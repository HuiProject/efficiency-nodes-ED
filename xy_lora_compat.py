"""统一 XY LoRA 规格辅助。XY 节点与 Loader 均使用三元组栈。"""


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
        result.append((first[0], 1.0 if first[1] is None else first[1],
                       1.0 if first[2] is None else first[2]))
    return result


def merge_partial_stack(partial_stack, base_stack=None):
    """逐项合并 XY 轴栈，支持 model/clip 单字段变化并保留另一轴结果。"""
    result = [normalize_entry(item[0], item[1], item[2]) for item in (base_stack or [])
              if item and item[0] != "None"]
    for item in partial_stack or []:
        result = merge_stack(item, result)
    return result


def stack_signature(stack):
    return tuple((str(n).replace("/", "\\").casefold(), round(float(m), 6), round(float(c), 6))
                 for n, m, c in stack or [])
