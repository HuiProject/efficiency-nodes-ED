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


def normalize_sweep_axis(axis):
    """Return ``(canonical_name, direction, field_mode)`` for Sweep axes.

    ``X``/``Y`` are accepted as compatibility aliases for pre-six-option
    workflows (model-on-X and clip-on-Y respectively).
    """
    raw = str(axis or "X Model").strip()
    canonical = {"X": "X Model", "Y": "Y Clip"}.get(raw.upper(), raw)
    specs = {
        "X Model": ("X", "model"),
        "X Clip": ("X", "clip"),
        "Y Model": ("Y", "model"),
        "Y Clip": ("Y", "clip"),
        "X Model and Clip": ("X", "both"),
        "Y Model and Clip": ("Y", "both"),
    }
    try:
        direction, mode = specs[canonical]
    except KeyError as exc:
        raise ValueError("LoRA Sweep 的 axis 必须是六种 Model/Clip 模式之一") from exc
    return canonical, direction, mode


# <2> 生成稳定栈签名，运行日志可据此判断是否发生乱序或重复应用。
def stack_fingerprint(stack):
    payload = [
        (normalize_name(name), round(float(model_strength), 6), round(float(clip_strength), 6))
        for name, model_strength, clip_strength in stack or []
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def _row_float(row_values, keys, fallback):
    """Read the first usable numeric value from a row, preserving old saves."""
    for key in keys:
        if key not in row_values or row_values[key] is None:
            continue
        try:
            return float(row_values[key])
        except (TypeError, ValueError):
            continue
    return float(fallback)


def normalize_sweep_rows(lora_count, row_values, max_rows=50):
    """Read only the active Stacker-style rows from a node input mapping.

    ``row_values`` is deliberately a plain mapping so the UI contract can be
    tested without importing ComfyUI. Hidden or stale rows outside count are
    ignored, and disabled/empty rows do not enter the sweep plan.  The return
    value is ``(name, model_first, model_last, clip_first, clip_last)``.
    The last two fields are optional in saved workflows and fall back to the
    model range, which preserves the pre-CLIP-axis behavior.
    """
    count = max(0, min(int(lora_count or 0), int(max_rows)))
    rows = []
    for index in range(1, count + 1):
        name = row_values.get(f"scan_lora_name_{index}")
        enabled = row_values.get(f"scan_lora_{index}_toggle", True)
        if not enabled or name in (None, "", "None"):
            continue
        first = _row_float(row_values, [f"scan_lora_first_strength_{index}"], 1.0)
        last = _row_float(row_values, [f"scan_lora_last_strength_{index}"], 1.0)
        clip_first = _row_float(
            row_values,
            [
                f"scan_lora_clip_first_strength_{index}",
                # Accept Plot-style aliases from early experimental saves.
                f"scan_lora_y_first_strength_{index}",
            ],
            first,
        )
        clip_last = _row_float(
            row_values,
            [
                f"scan_lora_clip_last_strength_{index}",
                f"scan_lora_y_last_strength_{index}",
            ],
            last,
        )
        rows.append((str(name), first, last, clip_first, clip_last))
    return count, rows


# <3> 保存 Power Loader 的基础对象、应用后对象和有序参数栈。
class EDLoraPipe:
    def __init__(self, base_model, base_clip, applied_model, applied_clip, stack,
                 available_loras=None):
        self.base_model = base_model
        self.base_clip = base_clip
        self.applied_model = applied_model
        self.applied_clip = applied_clip
        self.stack = [
            (str(name), float(model_strength), float(clip_strength))
            for name, model_strength, clip_strength in stack or []
        ]
        # Power Loader keeps disabled rows out of ``stack`` deliberately, but
        # legacy LoRA Plot may select one of those rows as a second-layer
        # overlay.  This metadata never participates in Sweep reconstruction.
        self.available_loras = [
            str(name) for name in (available_loras or [item[0] for item in self.stack])
            if name not in (None, "", "None")
        ]
        self.fingerprint = stack_fingerprint(self.stack)


# <4> 保存一个目标 LoRA 的单轴扫描，不携带或修改模型对象。
class EDLoraSweepPlan:
    def __init__(self, lora_pipe, target_name, values, target_specs=None,
                 axis_mode="both"):
        """Create an immutable scan plan.

        ``axis_mode`` is ``both`` for the existing LoRA Sweep node, and may be
        ``model``/``clip`` for the ED LoRA Plot adapter.  The latter two modes
        deliberately override only one half of a LoRA pair so an X/Y plot can
        reproduce the two-dimensional model-vs-clip workflow without applying
        either axis twice.
        """
        axis_mode = str(axis_mode or "both").lower()
        if axis_mode not in {"both", "model", "clip"}:
            raise ValueError(f"unsupported LoRA sweep axis mode: {axis_mode}")
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
        self.axis_mode = axis_mode
        self.targets = targets
        self.target_names = [item[0] for item in targets]
        self.target_name = ", ".join(self.target_names)
        self.values = [float(value) for value in values]
        self.model_ranges = {}
        self.clip_ranges = {}
        for spec in target_specs or []:
            if len(spec) < 3:
                continue
            name, model_first, model_last = spec[:3]
            clip_first = spec[3] if len(spec) >= 5 else model_first
            clip_last = spec[4] if len(spec) >= 5 else model_last
            key = normalize_name(name)
            self.model_ranges[key] = (float(model_first), float(model_last))
            self.clip_ranges[key] = (float(clip_first), float(clip_last))
        # ``target_ranges`` remains an alias for callers written against the
        # original three-value plan contract.
        self.target_ranges = self.model_ranges

    def axis_values(self):
        """Return one XY value per batch index, with independent ranges per LoRA."""
        result = []
        for index in range(len(self.values)):
            overrides = {}
            labels = []
            for target in self.targets:
                if self.axis_mode == "clip":
                    ranges = self.clip_ranges
                else:
                    ranges = self.model_ranges
                first, last = ranges.get(
                    normalize_name(target[0]), (self.values[0], self.values[-1])
                )
                count = max(1, len(self.values))
                value = first if count == 1 else first + (last - first) * index / (count - 1)
                overrides[normalize_name(target[0])] = value
                suffix = {"model": " MStr", "clip": " CStr", "both": ""}[self.axis_mode]
                labels.append(f"{target[0]}{suffix}={value:.6g}")
            result.append(EDLoraAxisValue(self, overrides, ", ".join(labels)))
        return result

    def stack_for_value(self, value):
        """只替换目标项，严格保留其他项目的顺序与强度。"""
        if isinstance(value, dict):
            overrides = {normalize_name(k): v for k, v in value.items()}
        else:
            overrides = {normalize_name(name): value for name in self.target_names}
        target_keys = set(overrides)
        result = []
        for name, model_strength, clip_strength in self.lora_pipe.stack:
            key = normalize_name(name)
            if key not in target_keys:
                result.append((name, float(model_strength), float(clip_strength)))
                continue
            raw = overrides[key]
            if isinstance(raw, (tuple, list)) and len(raw) >= 2:
                model_override, clip_override = raw[0], raw[1]
            elif self.axis_mode == "model":
                model_override, clip_override = raw, None
            elif self.axis_mode == "clip":
                model_override, clip_override = None, raw
            else:
                model_override = clip_override = raw
            result.append((
                name,
                float(model_strength) if model_override is None else float(model_override),
                float(clip_strength) if clip_override is None else float(clip_override),
            ))
        return result


class EDLoraAxisValue:
    """One value exposed to the standard XY Plot while retaining its ED plan."""
    def __init__(self, plan, value, label=None):
        self.plan = plan
        self.value = value
        self.label = label or f"{plan.target_name}={value}"


def combine_sweep_stacks(base_pipe, x_plan, x_value, y_plan=None, y_value=None):
    """Apply X and Y overrides to one immutable loader stack, preserving order."""
    # Store a pair of optional fields per normalized name.  This lets a model
    # axis and a clip axis target the same LoRA intentionally while still
    # rejecting conflicting overrides of the same field.
    overrides = {}
    for plan, value in ((x_plan, x_value), (y_plan, y_value)):
        if plan is None:
            continue
        pairs = value.items() if isinstance(value, dict) else ((name, value) for name in plan.target_names)
        for target_name, target_value in pairs:
            key = normalize_name(target_name)
            if isinstance(target_value, (tuple, list)) and len(target_value) >= 2:
                model_value, clip_value = target_value[0], target_value[1]
            elif getattr(plan, "axis_mode", "both") == "model":
                model_value, clip_value = target_value, None
            elif getattr(plan, "axis_mode", "both") == "clip":
                model_value, clip_value = None, target_value
            else:
                model_value = clip_value = target_value
            current = overrides.setdefault(key, [None, None])
            for position, incoming in enumerate((model_value, clip_value)):
                if incoming is None:
                    continue
                incoming = float(incoming)
                if current[position] is not None and abs(current[position] - incoming) > 1e-9:
                    field = "model" if position == 0 else "clip"
                    raise ValueError(
                        f"X/Y sweep targets the same LoRA {field} strength with different values: {target_name}"
                    )
                current[position] = incoming
    return [
        (name,
         float(model_strength) if overrides.get(normalize_name(name), [None, None])[0] is None
         else overrides[normalize_name(name)][0],
         float(clip_strength) if overrides.get(normalize_name(name), [None, None])[1] is None
         else overrides[normalize_name(name)][1])
        for name, model_strength, clip_strength in base_pipe.stack
    ]


def normalize_plot_rows(lora_count, row_values, max_rows=50):
    """Return enabled target names for the compact LoRA Plot UI.

    Plot ranges are node-level X/Y values, so rows intentionally carry only a
    name and toggle.  Accepting the Sweep row keys as aliases keeps workflows
    migrated from the Stacker-style editor readable without duplicating rows.
    """
    count = max(0, min(int(lora_count or 0), int(max_rows)))
    rows = []
    for index in range(1, count + 1):
        name = row_values.get(f"scan_lora_name_{index}")
        enabled = row_values.get(f"scan_lora_{index}_toggle", True)
        if enabled and name not in (None, "", "None"):
            rows.append(str(name))
    return count, rows


def _plot_float(row_values, key, fallback):
    """Read one persisted Plot range value without breaking old workflows."""
    value = row_values.get(key, fallback)
    if value is None:
        value = fallback
    return float(value)


def normalize_plot_range_rows(lora_count, row_values, x_first_default,
                              x_last_default, y_first_default, y_last_default,
                              max_rows=50):
    """Return enabled Plot rows with their own X/Y ranges.

    The default arguments are retained for the pure helper API, but the ED
    node now supplies a neutral ``1.0`` fallback and serializes four explicit
    values for every selected LoRA. This keeps interpolation independent per
    row and avoids a second global batch/range contract.
    """
    count = max(0, min(int(lora_count or 0), int(max_rows)))
    rows = []
    for index in range(1, count + 1):
        name = row_values.get(f"scan_lora_name_{index}")
        enabled = row_values.get(f"scan_lora_{index}_toggle", True)
        if not enabled or name in (None, "", "None"):
            continue
        rows.append((
            str(name),
            _plot_float(row_values, f"scan_lora_x_first_strength_{index}", x_first_default),
            _plot_float(row_values, f"scan_lora_x_last_strength_{index}", x_last_default),
            _plot_float(row_values, f"scan_lora_y_first_strength_{index}", y_first_default),
            _plot_float(row_values, f"scan_lora_y_last_strength_{index}", y_last_default),
        ))
    return count, rows


# <5> 生成包含首尾值的等距扫描。
def generate_sweep_values(count, first_value, last_value):
    count = int(count)
    if count <= 0:
        raise ValueError("扫描数量必须大于 0")
    if count == 1:
        return [float(first_value)]
    step = (float(last_value) - float(first_value)) / (count - 1)
    return [float(first_value) + step * index for index in range(count)]
