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
    from .xy_lora_compat import XYLoraAxisValue, LegacyOverlayAxisValue, make_axis_value, make_stack_sweep
    from .xy_lora_ed import (
        EDLoraPipe, EDLoraSweepPlan, generate_sweep_values,
        normalize_plot_rows, normalize_plot_range_rows, normalize_sweep_axis,
    )
except ImportError:  # pragma: no cover - direct development import
    from xy_inputs_ed import XYPLOT_DEF, XYPLOT_LIM, generate_floats
    from xy_lora_compat import XYLoraAxisValue, LegacyOverlayAxisValue, make_axis_value, make_stack_sweep
    from xy_lora_ed import (
        EDLoraPipe, EDLoraSweepPlan, generate_sweep_values,
        normalize_plot_rows, normalize_plot_range_rows, normalize_sweep_axis,
    )


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


def _validate_plot_targets(names, base_stack, lora_pipe=None):
    """Validate the Plot's second-layer candidates without changing Sweep.

    An overlay target may be present as a disabled row in Power Loader: it is
    intentionally absent from the applied stack but remains selectable through
    ``available_loras``.  A plain LORA_STACK has no row metadata, so it stays
    restricted to the supplied stack.
    """
    if lora_pipe is not None and getattr(lora_pipe, "available_loras", None):
        available = {
            str(name).replace("/", "\\").casefold()
            for name in lora_pipe.available_loras
        }
        missing = [name for name in names if str(name).replace("/", "\\").casefold() not in available]
        if missing:
            return (
                "LoRA Plot selection is not a row in the connected Power Loader: "
                + ", ".join(map(str, missing))
            )
        return None
    return _validate_stack_targets(names, base_stack)


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
    """ED-owned post-stack LoRA overlay axis.

    The node deliberately has one batch dimension and one XY_AXIS output, the
    same socket contract as ``XY Input: LoRA Sweep``.  It remains a separate
    execution mode because each cell applies the selected LoRAs on top of the
    already-applied Power Loader result.
    """

    MAX_SCAN_LORAS = 50

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "batch_count": ("INT", {"default": XYPLOT_DEF, "min": 1, "max": XYPLOT_LIM, "step": 1}),
            "lora_count": ("INT", {"default": 1, "min": 0, "max": cls.MAX_SCAN_LORAS, "step": 1}),
            "axis": ([
                "X Model", "X Clip", "Y Model", "Y Clip",
                "X Model and Clip", "Y Model and Clip",
            ], {"default": "X Model"}),
        }
        return {"required": required, "optional": _FlexiblePlotInputs({
            "lora_pipe": ("ED_LORA_PIPE",),
            "lora_stack": ("LORA_STACK",),
        })}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("XY_AXIS",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, batch_count, lora_count, axis="X Model",
                 lora_stack=None, lora_pipe=None, **kwargs):
        batch_count = max(1, min(int(batch_count), XYPLOT_LIM))
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        if not base_stack:
            raise ValueError("ED LoRA Plot requires a connected Power Loader ED LORA_PIPE/LORA_STACK")

        _, rows = normalize_plot_range_rows(
            lora_count, kwargs, 1.0, 1.0, 1.0, 1.0, self.MAX_SCAN_LORAS,
        )
        names = [row[0] for row in rows]
        if not rows:
            raise ValueError("ED LoRA Plot 至少需要一个已启用的 LoRA 行")
        error = _validate_plot_targets(names, base_stack, lora_pipe)
        if error:
            raise ValueError(error)

        axis_name, axis_direction, axis_mode = normalize_sweep_axis(axis)
        positions = generate_sweep_values(batch_count, 0.0, 1.0)

        def overlay_values(position, range_axis, mode="model"):
            entries = []
            labels = []
            for name, x_first, x_last, y_first, y_last in rows:
                if mode == "both":
                    model_value = float(x_first + (x_last - x_first) * float(position))
                    clip_value = float(y_first + (y_last - y_first) * float(position))
                    entries.append((name, model_value, clip_value))
                    labels.append(f"{name} MStr+CStr={model_value:.6g}/{clip_value:.6g}")
                    continue
                first, last = ((x_first, x_last) if range_axis == "x"
                               else (y_first, y_last))
                value = float(first + (last - first) * float(position))
                model_value = value if mode in {"model", "both"} else None
                clip_value = value if mode in {"clip", "both"} else None
                entries.append((name, model_value, clip_value))
                suffix = "MStr" if mode == "model" else "CStr" if mode == "clip" else "MStr+CStr"
                labels.append(f"{name} {suffix}={value:.6g}")
            suffix = "MStr" if mode == "model" else "CStr" if mode == "clip" else "MStr+CStr"
            return LegacyOverlayAxisValue(entries, ", ".join(labels))

        axis_type = "ED_LORA_SWEEP_X" if axis_direction == "X" else "ED_LORA_SWEEP_Y"
        # The two visible pairs are weight fields, not directions: Model is
        # always the x-range pair and CLIP is always the y-range pair. The
        # direction only decides whether this one axis is emitted to XY Plot.X
        # or XY Plot.Y.
        range_axis = "x" if axis_mode == "model" else "y"
        axis_values = [overlay_values(position, range_axis, axis_mode) for position in positions]
        print(
            f"[ED-XY-PLOT] stack count={len(base_stack)} "
            f"rows={rows} mode=legacy-overlay axis={axis_name} "
            f"values={[v.label for v in axis_values]}"
        )
        return ((axis_type, axis_values),)

    @classmethod
    def VALIDATE_INPUTS(cls, batch_count=1, lora_count=0, lora_stack=None, lora_pipe=None, **kwargs):
        base_stack = _stack_from_inputs(lora_stack, lora_pipe)
        _, names = normalize_plot_rows(lora_count, kwargs, cls.MAX_SCAN_LORAS)
        if not names:
            return "ED LoRA Plot requires at least one enabled LoRA row"
        return _validate_plot_targets(names, base_stack, lora_pipe) or True


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
