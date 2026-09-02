"""统一 XY LoRA 规格辅助。XY 节点与 Loader 均使用三元组栈。"""


class XYLoraAxisValue(list):
    """携带单轴修改意图，同时保持与旧版 LORA_STACK 的列表兼容。"""

    def __init__(self, resolved_stack, target_name, model_override, clip_override,
                 default_model, default_clip, base_stack):
        super().__init__(resolved_stack)
        self.target_name = str(target_name)
        self.model_override = model_override
        self.clip_override = clip_override
        self.default_model = float(default_model)
        self.default_clip = float(default_clip)
        self.base_stack = [tuple(item) for item in (base_stack or [])]
        model_label = "*" if model_override is None else f"{float(model_override):.6g}"
        clip_label = "*" if clip_override is None else f"{float(clip_override):.6g}"
        self.label = f"{self.target_name}={model_label}/{clip_label}"


def normalize_entry(name, model_strength=1.0, clip_strength=1.0):
    if not name or name == "None":
        return None
    return (str(name), None if model_strength is None else float(model_strength),
            None if clip_strength is None else float(clip_strength))


def merge_stack(primary, base_stack=None):
    """以 primary 替换同名基础项并保留原顺序；不存在时追加到末尾。"""
    first = normalize_entry(*primary)
    if first is None:
        return [tuple(item) for item in (base_stack or []) if item and item[0] != "None"]
    key = first[0].replace("/", "\\").casefold()
    result = []
    replaced = False
    for item in base_stack or []:
        if not item or item[0] == "None":
            continue
        item_key = str(item[0]).replace("/", "\\").casefold()
        if item_key == key:
            if not replaced:
                # None 表示该轴不修改此字段，保留基础栈当前值。
                result.append((item[0],
                               item[1] if first[1] is None else first[1],
                               item[2] if first[2] is None else first[2]))
                replaced = True
            continue
        result.append(normalize_entry(item[0], item[1], item[2]))
    if not replaced:
        # 与 LoRA Stacker 一致：本节点选择的 LoRA 位于输入基础栈之前。
        result.insert(0, (first[0], 1.0 if first[1] is None else first[1],
                          1.0 if first[2] is None else first[2]))
    return result


def make_axis_value(primary, base_stack=None, default_model=1.0, default_clip=1.0):
    """生成带修改掩码的轴值；None 字段直到最终网格合并前都不会被填充。"""
    name, model_override, clip_override = normalize_entry(*primary)
    resolved = merge_stack((name,
                            default_model if model_override is None else model_override,
                            default_clip if clip_override is None else clip_override), base_stack)
    return XYLoraAxisValue(resolved, name, model_override, clip_override,
                           default_model, default_clip, base_stack)


def make_stack_sweep(target_name, base_stack, values):
    """只扫描连接栈内已有 LoRA；强度同时作用于 model 和 clip。"""
    target_key = str(target_name).replace("/", "\\").casefold()
    target = next(
        (item for item in (base_stack or [])
         if item and str(item[0]).replace("/", "\\").casefold() == target_key),
        None,
    )
    if target is None:
        raise ValueError(f"Target LoRA is not enabled in the connected stack: {target_name}")

    return [make_axis_value((target[0], value, value), base_stack, target[1], target[2])
            for value in values]


def merge_partial_stack(partial_stack, base_stack=None):
    """逐项合并 XY 轴栈，支持 model/clip 单字段变化并保留另一轴结果。"""
    if isinstance(partial_stack, XYLoraAxisValue):
        result = [normalize_entry(item[0], item[1], item[2])
                  for item in (base_stack or partial_stack.base_stack)
                  if item and item[0] != "None"]
        key = partial_stack.target_name.replace("/", "\\").casefold()
        current = next((item for item in result
                        if str(item[0]).replace("/", "\\").casefold() == key), None)
        model_strength = current[1] if current is not None else partial_stack.default_model
        clip_strength = current[2] if current is not None else partial_stack.default_clip
        if partial_stack.model_override is not None:
            model_strength = float(partial_stack.model_override)
        if partial_stack.clip_override is not None:
            clip_strength = float(partial_stack.clip_override)
        return merge_stack((partial_stack.target_name, model_strength, clip_strength), result)

    result = [normalize_entry(item[0], item[1], item[2]) for item in (base_stack or [])
              if item and item[0] != "None"]
    for item in partial_stack or []:
        result = merge_stack(item, result)
    return result


def stack_signature(stack):
    return tuple((str(n).replace("/", "\\").casefold(), round(float(m), 6), round(float(c), 6))
                 for n, m, c in stack or [])
