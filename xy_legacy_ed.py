"""ED-owned compatibility nodes for the legacy LoRA XY input contract.

The historical nodes exposed fifty fixed rows and returned ``XY`` tuples.
These adapters keep that serialization contract, but their values carry an
immutable stack override understood by ED's sampler.  No legacy plugin code
is imported at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path

import folder_paths

try:
    from .xy_inputs_ed import XYPLOT_DEF, XYPLOT_LIM, generate_floats
    from .xy_lora_compat import XYLoraAxisValue, make_axis_value, make_stack_sweep
except ImportError:  # pragma: no cover - direct development import
    from xy_inputs_ed import XYPLOT_DEF, XYPLOT_LIM, generate_floats
    from xy_lora_compat import XYLoraAxisValue, make_axis_value, make_stack_sweep


LORA_MODES = ["LoRA Names", "LoRA Names+Weights", "LoRA Batch"]
LORA_EXTENSIONS = (".safetensors", ".ckpt")


def _stack_from_inputs(lora_stack=None, lora_pipe=None):
    if lora_pipe is not None and getattr(lora_pipe, "stack", None) is not None:
        return [tuple(item) for item in lora_pipe.stack]
    return [tuple(item) for item in (lora_stack or []) if item and item[0] != "None"]


def _row_values(kwargs, count, mode, model_strength, clip_strength):
    rows = []
    for index in range(1, max(0, min(int(count), XYPLOT_LIM)) + 1):
        name = kwargs.get(f"lora_name_{index}")
        if not name or name == "None":
            continue
        if "Weights" in mode:
            model = kwargs.get(f"model_str_{index}", model_strength)
            clip = kwargs.get(f"clip_str_{index}", clip_strength)
        else:
            model, clip = model_strength, clip_strength
        rows.append((str(name), float(model), float(clip)))
    return rows


def _batch_files(path, sort_order, batch_max, include_subdirectories=False):
    root = Path(str(path or ""))
    if not root.is_dir():
        raise ValueError(f"LoRA batch path does not exist: {root}")
    iterator = root.rglob("*") if include_subdirectories else root.iterdir()
    values = [str(item) for item in iterator if item.is_file() and item.suffix.lower() in LORA_EXTENSIONS]
    values.sort(reverse=str(sort_order) == "descending")
    if int(batch_max) != -1:
        values = values[:max(0, int(batch_max))]
    return values


def _axis_values(rows, base_stack):
    return [make_axis_value(row, base_stack, row[1], row[2]) for row in rows]


def _validate_stack_targets(names, base_stack):
    """Reject global-list selections when a connected stack is authoritative."""
    if not base_stack:
        return None
    available = {str(item[0]).replace("/", "\\").casefold() for item in base_stack if item}
    missing = [name for name in names if name and name != "None"
               and str(name).replace("/", "\\").casefold() not in available]
    if missing:
        return (
            "LoRA XY selection is not in the connected Power Loader stack: "
            + ", ".join(map(str, missing))
        )
    return None


class LegacyXYLoraED:
    """Drop-in ``XY Input: LoRA`` with ED-owned stack semantics."""

    @classmethod
    def INPUT_TYPES(cls):
        loras = ["None"] + folder_paths.get_filename_list("loras")
        required = {
            "input_mode": (LORA_MODES,),
            "batch_path": ("STRING", {"default": os.path.abspath(os.sep) + "example_folder", "multiline": False}),
            "subdirectories": ("BOOLEAN", {"default": False}),
            "batch_sort": (["ascending", "descending"],),
            "batch_max": ("INT", {"default": -1, "min": -1, "max": XYPLOT_LIM, "step": 1}),
            "lora_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM, "step": 1}),
            "model_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "clip_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
        }
        for index in range(1, XYPLOT_LIM + 1):
            required[f"lora_name_{index}"] = (loras,)
            required[f"model_str_{index}"] = ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01})
            required[f"clip_str_{index}"] = ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01})
        return {"required": required, "optional": {
            "lora_stack": ("LORA_STACK",),
            "lora_pipe": ("ED_LORA_PIPE",),
        }}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, input_mode, batch_path, subdirectories, batch_sort, batch_max,
                 lora_count, model_strength, clip_strength, lora_stack=None,
                 lora_pipe=None, **kwargs):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        if "Batch" in input_mode:
            names = _batch_files(batch_path, batch_sort, batch_max, subdirectories)
            rows = [(name, model_strength, clip_strength) for name in names]
        else:
            rows = _row_values(kwargs, lora_count, input_mode, model_strength, clip_strength)
            if int(batch_max) != -1:
                rows = rows[:max(0, int(batch_max))]
        if not rows:
            print("[ED-XY] legacy LoRA input produced no rows")
            return (None,)
        values = _axis_values(rows, base_stack)
        print(f"[ED-XY] legacy LoRA rows={len(values)} base_stack={len(base_stack)}")
        return (("LoRA", values),)

    @classmethod
    def VALIDATE_INPUTS(cls, lora_count=0, lora_stack=None, lora_pipe=None, **kwargs):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        names = [kwargs.get(f"lora_name_{index}")
                 for index in range(1, max(0, min(int(lora_count), XYPLOT_LIM)) + 1)]
        return _validate_stack_targets(names, base_stack) or True


class LegacyXYLoraPlotED:
    """Drop-in ``XY Input: LoRA Plot`` using ED immutable stack values."""

    modes = [
        "X: LoRA Batch, Y: LoRA Weight",
        "X: LoRA Batch, Y: Model Strength",
        "X: LoRA Batch, Y: Clip Strength",
        "X: Model Strength, Y: Clip Strength",
        "X: Connected Stack LoRA Strength",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        loras = ["None"] + folder_paths.get_filename_list("loras")
        return {"required": {
            "input_mode": (cls.modes,),
            "lora_name": (loras,),
            "model_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "clip_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "X_batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "X_batch_path": ("STRING", {"default": os.path.abspath(os.sep) + "example_folder", "multiline": False}),
            "X_subdirectories": ("BOOLEAN", {"default": False}),
            "X_batch_sort": (["ascending", "descending"],),
            "X_first_value": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "X_last_value": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "Y_batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "Y_first_value": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "Y_last_value": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
        }, "optional": {
            "lora_stack": ("LORA_STACK",),
            "lora_pipe": ("ED_LORA_PIPE",),
        }}

    RETURN_TYPES = ("XY", "XY")
    RETURN_NAMES = ("X", "Y")
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, input_mode, lora_name, model_strength, clip_strength,
                 X_batch_count, X_batch_path, X_subdirectories, X_batch_sort,
                 X_first_value, X_last_value, Y_batch_count, Y_first_value,
                 Y_last_value, lora_stack=None, lora_pipe=None):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        if input_mode == "X: Connected Stack LoRA Strength":
            if not base_stack:
                raise ValueError("ED LoRA Plot connected-stack mode requires LORA_STACK or ED_LORA_PIPE")
            values = generate_floats(X_batch_count, X_first_value, X_last_value)
            result = make_stack_sweep(lora_name, base_stack, values)
            print(f"[ED-XY] legacy connected LoRA target={lora_name} values={values}")
            return (("LoRA Wt", result), None)

        x_values, y_values = [], []
        x_type = "Nothing"
        if "X: LoRA Batch" in input_mode:
            names = _batch_files(X_batch_path, X_batch_sort, X_batch_count, X_subdirectories)
            x_values = _axis_values([(name, model_strength, clip_strength) for name in names], base_stack)
            x_type = "LoRA"
        elif "X: Model Strength" in input_mode:
            x_values = [make_axis_value((lora_name, value, None), base_stack, model_strength, clip_strength)
                        for value in generate_floats(X_batch_count, X_first_value, X_last_value)]
            x_type = "LoRA MStr"

        y_values_raw = generate_floats(Y_batch_count, Y_first_value, Y_last_value)
        if "Y: LoRA Weight" in input_mode:
            y_values = [make_axis_value((lora_name, value, value), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
            y_type = "LoRA Wt"
        elif "Y: Model Strength" in input_mode:
            y_values = [make_axis_value((lora_name, value, None), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
            y_type = "LoRA MStr"
        else:
            y_values = [make_axis_value((lora_name, None, value), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
            y_type = "LoRA CStr"
        if lora_name == "None":
            raise ValueError("ED LoRA Plot requires a LoRA selection")
        print(f"[ED-XY] legacy LoRA Plot X={x_type}:{len(x_values)} Y={y_type}:{len(y_values)} stack={len(base_stack)}")
        return ((x_type, x_values), (y_type, y_values))

    @classmethod
    def VALIDATE_INPUTS(cls, lora_name="None", lora_stack=None, lora_pipe=None, **kwargs):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        return _validate_stack_targets([lora_name], base_stack) or True


class LegacyXYAestheticScoreED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "target_ascore": (["positive", "negative"],),
            "batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "first_ascore": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1000.0, "step": 0.01}),
            "last_ascore": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 1000.0, "step": 0.01}),
        }}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, target_ascore, batch_count, first_ascore, last_ascore):
        values = generate_floats(batch_count, first_ascore, last_ascore)
        return (("AScore+" if target_ascore == "positive" else "AScore-", values),) if values else (None,)


NODE_CLASS_MAPPINGS = {
    "XY Input: LoRA": LegacyXYLoraED,
    "XY Input: LoRA Plot": LegacyXYLoraPlotED,
    "XY Input: Aesthetic Score": LegacyXYAestheticScoreED,
}


__all__ = ["XYLoraAxisValue", "LegacyXYLoraED", "LegacyXYLoraPlotED",
           "LegacyXYAestheticScoreED", "NODE_CLASS_MAPPINGS"]
