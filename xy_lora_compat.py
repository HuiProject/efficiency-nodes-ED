"""统一 XY LoRA 规格辅助。XY 节点与 Loader 均使用三元组栈。"""


def normalize_entry(name, model_strength=1.0, clip_strength=1.0):
    if not name or name == "None":
        return None
    return (str(name), float(model_strength), float(clip_strength))


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
                result.append(first)
                replaced = True
            continue
        result.append(normalize_entry(item[0], item[1], item[2]))
    if not replaced:
        result.append(first)
    return result


def stack_signature(stack):
    return tuple((str(n).replace("/", "\\").casefold(), round(float(m), 6), round(float(c), 6))
                 for n, m, c in stack or [])
