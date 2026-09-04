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
    from .xy_lora_ed import EDLoraPipe, EDLoraSweepPlan, generate_sweep_values, normalize_plot_rows
except ImportError:  # pragma: no cover - direct development import
    from xy_inputs_ed import XYPLOT_DEF, XYPLOT_LIM, generate_floats
    from xy_lora_compat import XYLoraAxisValue, make_axis_value, make_stack_sweep
    from xy_lora_ed import EDLoraPipe, EDLoraSweepPlan, generate_sweep_values, normalize_plot_rows


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


class _FlexiblePlotInputs(dict):
    """Accept dynamic scan_lora_* widgets created by the local frontend."""
    def __getitem__(self, key):
        return dict.__getitem__(self, key) if dict.__contains__(self, key) else ("*",)

    def __contains__(self, key):
        return True


class LegacyXYLoraPlotED:
    """Compact ED ``XY Input: LoRA Plot`` with stack-derived target rows."""

    MAX_SCAN_LORAS = 50
    LEGACY_MODES = {
        "X: LoRA Batch, Y: LoRA Weight",
        "X: LoRA Batch, Y: Model Strength",
        "X: LoRA Batch, Y: Clip Strength",
        "X: Model Strength, Y: Clip Strength",
        "X: Connected Stack LoRA Strength",
    }

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "lora_count": ("INT", {"default": 1, "min": 0, "max": cls.MAX_SCAN_LORAS, "step": 1}),
            "X_batch_count": ("INT", {"default": XYPLOT_DEF, "min": 1, "max": XYPLOT_LIM, "step": 1}),
            "X_first_value": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "X_last_value": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "Y_batch_count": ("INT", {"default": XYPLOT_DEF, "min": 1, "max": XYPLOT_LIM, "step": 1}),
            "Y_first_value": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "Y_last_value": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
        }
        return {"required": required, "optional": _FlexiblePlotInputs({
            "lora_pipe": ("ED_LORA_PIPE",),
            "lora_stack": ("LORA_STACK",),
        })}

    RETURN_TYPES = ("XY", "XY")
    RETURN_NAMES = ("X", "Y")
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, *args, lora_count=None, X_batch_count=None,
                 X_first_value=None, X_last_value=None, Y_batch_count=None,
                 Y_first_value=None, Y_last_value=None, lora_stack=None,
                 lora_pipe=None, **kwargs):
        # Saved graphs from the historical plugin may still submit the old
        # positional contract.  Keep a narrow compatibility branch while the
        # visible INPUT_TYPES remains the compact ED contract.
        if args and isinstance(args[0], str) and args[0] in self.LEGACY_MODES:
            legacy = list(args) + [None] * 13
            (input_mode, lora_name, model_strength, clip_strength,
             old_x_count, old_path, old_subdirs, old_sort, old_x_first,
             old_x_last, old_y_count, old_y_first, old_y_last) = legacy[:13]
            return self._legacy_xy_value(
                input_mode, lora_name, model_strength, clip_strength,
                old_x_count, old_path, old_subdirs, old_sort, old_x_first,
                old_x_last, old_y_count, old_y_first, old_y_last,
                lora_stack=lora_stack, lora_pipe=lora_pipe,
            )
        if "input_mode" in kwargs or "lora_name" in kwargs:
            return self._legacy_xy_value(
                kwargs.get("input_mode", "X: Model Strength, Y: Clip Strength"),
                kwargs.get("lora_name", "None"), kwargs.get("model_strength", 1.0),
                kwargs.get("clip_strength", 1.0), kwargs.get("X_batch_count", XYPLOT_DEF),
                kwargs.get("X_batch_path", ""), kwargs.get("X_subdirectories", False),
                kwargs.get("X_batch_sort", "ascending"), kwargs.get("X_first_value", 0.0),
                kwargs.get("X_last_value", 1.0), kwargs.get("Y_batch_count", XYPLOT_DEF),
                kwargs.get("Y_first_value", 0.0), kwargs.get("Y_last_value", 1.0),
                lora_stack=lora_stack, lora_pipe=lora_pipe,
            )
        if lora_count is None:
            lora_count = 0
        X_batch_count = XYPLOT_DEF if X_batch_count is None else X_batch_count
        X_first_value = 0.0 if X_first_value is None else X_first_value
        X_last_value = 1.0 if X_last_value is None else X_last_value
        Y_batch_count = XYPLOT_DEF if Y_batch_count is None else Y_batch_count
        Y_first_value = 0.0 if Y_first_value is None else Y_first_value
        Y_last_value = 1.0 if Y_last_value is None else Y_last_value
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        if not base_stack:
            raise ValueError("ED LoRA Plot requires a connected Power Loader ED LORA_PIPE/LORA_STACK")

        _, names = normalize_plot_rows(lora_count, kwargs, self.MAX_SCAN_LORAS)
        if not names:
            raise ValueError("ED LoRA Plot 至少需要一个已启用的 LoRA 行")
        error = _validate_stack_targets(names, base_stack)
        if error:
            raise ValueError(error)

        # A plan needs the immutable base pipe.  When only the legacy
        # LORA_STACK socket is connected, create a metadata-only pipe; the
        # sampler will prefer the real pipe carried by Efficient Loader's
        # context at execution time.
        pipe = lora_pipe or EDLoraPipe(None, None, None, None, base_stack)
        x_specs = [(name, float(X_first_value), float(X_last_value)) for name in names]
        y_specs = [(name, float(Y_first_value), float(Y_last_value)) for name in names]
        x_plan = EDLoraSweepPlan(
            pipe, names, generate_sweep_values(X_batch_count, 0.0, 1.0),
            target_specs=x_specs, axis_mode="model",
        )
        y_plan = EDLoraSweepPlan(
            pipe, names, generate_sweep_values(Y_batch_count, 0.0, 1.0),
            target_specs=y_specs, axis_mode="clip",
        )
        x_axis = ("ED_LORA_SWEEP_X", x_plan.axis_values())
        y_axis = ("ED_LORA_SWEEP_Y", y_plan.axis_values())
        print(
            f"[ED-XY-PLOT] stack count={len(base_stack)} "
            f"targets={names} X values={[v.label for v in x_plan.axis_values()]} "
            f"Y values={[v.label for v in y_plan.axis_values()]}"
        )
        return (x_axis, y_axis)

    def _legacy_xy_value(self, input_mode, lora_name, model_strength, clip_strength,
                         X_batch_count, X_batch_path, X_subdirectories, X_batch_sort,
                         X_first_value, X_last_value, Y_batch_count, Y_first_value,
                         Y_last_value, lora_stack=None, lora_pipe=None):
        """Evaluate only old serialized calls; new UI never exposes these fields."""
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        if input_mode == "X: Connected Stack LoRA Strength":
            if not base_stack:
                raise ValueError("ED LoRA Plot connected-stack mode requires LORA_STACK or ED_LORA_PIPE")
            values = generate_floats(X_batch_count, X_first_value, X_last_value)
            return (("LoRA Wt", make_stack_sweep(lora_name, base_stack, values)), None)
        if lora_name == "None":
            raise ValueError("ED LoRA Plot requires a LoRA selection")
        if "LoRA Batch" in input_mode:
            names = _batch_files(X_batch_path, X_batch_sort, X_batch_count, X_subdirectories)
            x_values = _axis_values([(name, model_strength, clip_strength) for name in names], base_stack)
            x_type = "LoRA Batch"
        else:
            x_values = [make_axis_value((lora_name, value, None), base_stack, model_strength, clip_strength)
                        for value in generate_floats(X_batch_count, X_first_value, X_last_value)]
            x_type = "LoRA MStr"
        y_values_raw = generate_floats(Y_batch_count, Y_first_value, Y_last_value)
        if "LoRA Weight" in input_mode:
            y_type = "LoRA Wt"
            y_values = [make_axis_value((lora_name, value, value), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
        elif "Model Strength" in input_mode:
            y_type = "LoRA MStr"
            y_values = [make_axis_value((lora_name, value, None), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
        else:
            y_type = "LoRA CStr"
            y_values = [make_axis_value((lora_name, None, value), base_stack, model_strength, clip_strength)
                        for value in y_values_raw]
        print(f"[ED-XY-PLOT] legacy compatibility X={x_type}:{len(x_values)} Y={y_type}:{len(y_values)}")
        return ((x_type, x_values), (y_type, y_values))

    @classmethod
    def VALIDATE_INPUTS(cls, lora_count=0, lora_stack=None, lora_pipe=None, **kwargs):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        _, names = normalize_plot_rows(lora_count, kwargs, cls.MAX_SCAN_LORAS)
        if not names:
            return "ED LoRA Plot requires at least one enabled LoRA row"
        return _validate_stack_targets(names, base_stack) or True


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
