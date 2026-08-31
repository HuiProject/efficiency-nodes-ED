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
    def __init__(self, lora_pipe, target_name, values):
        target_key = normalize_name(target_name)
        target = next(
            (item for item in lora_pipe.stack if normalize_name(item[0]) == target_key),
            None,
        )
        if target is None:
            raise ValueError(f"目标 LoRA 未启用或不在连接栈中: {target_name}")
        if not values:
            raise ValueError("LoRA 扫描至少需要一个强度值")

        self.lora_pipe = lora_pipe
        self.target_name = target[0]
        self.values = [float(value) for value in values]

    def stack_for_value(self, value):
        """只替换目标项，严格保留其他项目的顺序与强度。"""
        target_key = normalize_name(self.target_name)
        return [
            (name, float(value), float(value))
            if normalize_name(name) == target_key
            else (name, float(model_strength), float(clip_strength))
            for name, model_strength, clip_strength in self.lora_pipe.stack
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
