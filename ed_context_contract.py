"""Local, testable helpers for the ED context transport contract.

The payload itself stays a plain dictionary so it remains compatible with
ComfyUI's ``RGTHREE_CONTEXT`` transport type. Keeping the merge and output
ordering here prevents nodes from accidentally dropping ED-only fields while
passing a context through the workflow.
"""


def build_context_io(context_data, force_input_types=(), force_input_names=()):
    """Build ComfyUI input/output metadata from one ordered field contract."""
    optional_inputs = {}
    return_types = ["RGTHREE_CONTEXT"]
    return_names = ["CONTEXT"]
    forced_types = set(force_input_types)
    forced_names = set(force_input_names)

    for key, (input_name, input_type, output_name) in context_data.items():
        options = {"forceInput": True} if (
            (isinstance(input_type, str) and input_type in forced_types)
            or input_name in forced_names
        ) else None
        optional_inputs[input_name] = (input_type, options) if options else (input_type,)
        if key != "base_ctx":
            return_types.append(input_type)
            return_names.append(output_name)

    return optional_inputs, tuple(return_types), tuple(return_names)


def new_context(context_data, base_ctx=None, **kwargs):
    """Return a fresh context while preserving every declared field from base."""
    base = base_ctx or {}
    result = {}
    for key in context_data:
        if key == "base_ctx":
            continue
        value = kwargs.get(key)
        result[key] = value if value is not None else base.get(key)
    return result


def context_to_tuple(context_data, context, inputs_list=None):
    """Return CONTEXT followed by fields in the stable socket order."""
    keys = context_data.keys() if inputs_list is None else inputs_list
    context = context or {}
    values = [context]
    for key in keys:
        if key != "base_ctx":
            values.append(context.get(key))
    return tuple(values)
