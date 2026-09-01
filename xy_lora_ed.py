"""ED 原生 LoRA XY 数据结构。

该模块不加载模型，只保存基础对象、有序 LoRA 栈和扫描计划，避免旧 XY 引擎
在另一个缓存及提示词编码流程中重建 Anima 模型。
"""

from __future__ import annotations

import hashlib
import json


# <1> 标准化 LoRA 名称，用于 Windows 路径大小写无关比较。
def normalize_name(name):
    return str(name).replace("/", "\\").casefold()


# <2> 生成稳定栈签名，运行日志可据此判断是否发生乱序或重复应用。
def stack_fingerprint(stack):
    payload = [
        (normalize_name(name), round(float(model_strength), 6), round(float(clip_strength), 6))
        for name, model_strength, clip_strength in stack or []
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def normalize_sweep_rows(lora_count, row_values, max_rows=50):
    """Read only the active Stacker-style rows from a node input mapping.

    ``row_values`` is deliberately a plain mapping so the UI contract can be
    tested without importing ComfyUI. Hidden or stale rows outside count are
    ignored, and disabled/empty rows do not enter the sweep plan.
    """
    count = max(0, min(int(lora_count or 0), int(max_rows)))
    rows = []
    for index in range(1, count + 1):
        name = row_values.get(f"scan_lora_name_{index}")
        enabled = row_values.get(f"scan_lora_{index}_toggle", True)
        if not enabled or name in (None, "", "None"):
            continue
        first = row_values.get(f"scan_lora_first_strength_{index}", 0.5)
        last = row_values.get(f"scan_lora_last_strength_{index}", 1.0)
        rows.append((str(name), float(first), float(last)))
    return count, rows


# <3> 保存 Power Loader 的基础对象、应用后对象和有序参数栈。
class EDLoraPipe:
    def __init__(self, base_model, base_clip, applied_model, applied_clip, stack):
        self.base_model = base_model
        self.base_clip = base_clip
        self.applied_model = applied_model
        self.applied_clip = applied_clip
        self.stack = [
            (str(name), float(model_strength), float(clip_strength))
            for name, model_strength, clip_strength in stack or []
        ]
        self.fingerprint = stack_fingerprint(self.stack)


# <4> 保存一个目标 LoRA 的单轴扫描，不携带或修改模型对象。
class EDLoraSweepPlan:
    def __init__(self, lora_pipe, target_name, values, target_specs=None):
        requested = [target_name] if isinstance(target_name, str) else list(target_name or [])
        if target_specs:
            requested = [spec[0] for spec in target_specs]
        requested = [str(name) for name in requested if name and str(name) != "None"]
        targets = []
        for name in requested:
            target_key = normalize_name(name)
            target = next((item for item in lora_pipe.stack if normalize_name(item[0]) == target_key), None)
            if target is None:
                raise ValueError(f"目标 LoRA 未启用或不在连接栈中: {name}")
            if all(normalize_name(target[0]) != normalize_name(item[0]) for item in targets):
                targets.append(target)
        if not targets:
            raise ValueError("至少需要选择一个用于扫描的 LoRA")
        if not values:
            raise ValueError("LoRA 扫描至少需要一个强度值")

        self.lora_pipe = lora_pipe
        self.targets = targets
        self.target_names = [item[0] for item in targets]
        self.target_name = ", ".join(self.target_names)
        self.values = [float(value) for value in values]
        self.target_ranges = {
            normalize_name(name): (float(first), float(last))
            for name, first, last in (target_specs or [])
        }

    def axis_values(self):
        """Return one XY value per batch index, with independent ranges per LoRA."""
        result = []
        for index in range(len(self.values)):
            overrides = {}
            labels = []
            for target in self.targets:
                first, last = self.target_ranges.get(normalize_name(target[0]), (self.values[0], self.values[-1]))
                count = max(1, len(self.values))
                value = first if count == 1 else first + (last - first) * index / (count - 1)
                overrides[normalize_name(target[0])] = value
                labels.append(f"{target[0]}={value:.6g}")
            result.append(EDLoraAxisValue(self, overrides, ", ".join(labels)))
        return result

    def stack_for_value(self, value):
        """只替换目标项，严格保留其他项目的顺序与强度。"""
        if isinstance(value, dict):
            overrides = {normalize_name(k): float(v) for k, v in value.items()}
        else:
            overrides = {normalize_name(name): float(value) for name in self.target_names}
        target_keys = set(overrides)
        return [
            (name, overrides[normalize_name(name)], overrides[normalize_name(name)])
            if normalize_name(name) in target_keys
            else (name, float(model_strength), float(clip_strength))
            for name, model_strength, clip_strength in self.lora_pipe.stack
        ]


class EDLoraAxisValue:
    """One value exposed to the standard XY Plot while retaining its ED plan."""
    def __init__(self, plan, value, label=None):
        self.plan = plan
        self.value = value
        self.label = label or f"{plan.target_name}={value}"


def combine_sweep_stacks(base_pipe, x_plan, x_value, y_plan=None, y_value=None):
    """Apply X and Y overrides to one immutable loader stack, preserving order."""
    overrides = {}
    for plan, value in ((x_plan, x_value), (y_plan, y_value)):
        if plan is None:
            continue
        pairs = value.items() if isinstance(value, dict) else ((name, value) for name in plan.target_names)
        for target_name, target_value in pairs:
            key = normalize_name(target_name)
            if key in overrides and abs(overrides[key] - float(target_value)) > 1e-9:
                raise ValueError(f"X/Y sweep targets the same LoRA with different values: {target_name}")
            overrides[key] = float(target_value)
    return [
        (name, overrides.get(normalize_name(name), float(model_strength)),
         overrides.get(normalize_name(name), float(clip_strength)))
        for name, model_strength, clip_strength in base_pipe.stack
    ]


# <5> 生成包含首尾值的等距扫描。
def generate_sweep_values(count, first_value, last_value):
    count = int(count)
    if count <= 0:
        raise ValueError("扫描数量必须大于 0")
    if count == 1:
        return [float(first_value)]
    step = (float(last_value) - float(first_value)) / (count - 1)
    return [float(first_value) + step * index for index in range(count)]
