"""ED-owned XY Plot script composer.

This node intentionally only composes the ``xyplot`` script consumed by ED's
sampler. It does not import or proxy the legacy efficiency-nodes plugin.
"""

from __future__ import annotations

try:
    from .xy_lora_compat import XYLoraAxisValue
except ImportError:  # pragma: no cover - direct development import
    from xy_lora_compat import XYLoraAxisValue

ED_LORA_TYPES = {"ED_LORA_SWEEP_X", "ED_LORA_SWEEP_Y"}
LEGACY_LORA_TYPES = {"LoRA", "LoRA Stacks", "LoRA Batch", "LoRA Wt", "LoRA MStr", "LoRA CStr"}
LORA_PLOT_TYPES = {"LoRA Batch", "LoRA Wt", "LoRA MStr", "LoRA CStr"}
ENCODE_TYPES = {
    "Checkpoint", "Refiner", "LoRA", "LoRA Stacks", "LoRA Batch", "LoRA Wt",
    "LoRA MStr", "LoRA CStr", "Positive Prompt S/R", "Negative Prompt S/R",
    "AScore+", "AScore-", "Clip Skip", "Clip Skip (Refiner)",
    "ControlNetStrength", "ControlNetStart%", "ControlNetEnd%",
}


def _error(message):
    print(f"[ED-XY] {message}")


def _unpack_axis(axis, default_type="Nothing"):
    if axis is None:
        return default_type, [""]
    if not isinstance(axis, (tuple, list)) or len(axis) != 2:
        raise ValueError(f"invalid XY axis payload: {axis!r}")
    axis_type, axis_values = axis
    return str(axis_type), list(axis_values or [])


def compose_xyplot_script(grid_spacing, xy_flip, y_label_orientation,
                          cache_models, ksampler_output_image,
                          my_unique_id, dependencies=None, X=None, Y=None):
    """Pack two XY axes into the legacy-compatible ED script tuple."""
    x_type, x_values = _unpack_axis(X)
    y_type, y_values = _unpack_axis(Y)
    dependency_state = "connected" if dependencies is not None else "missing"
    print(
        f"[ED-XY-PLOT] compose X={x_type}:{len(x_values)} "
        f"Y={y_type}:{len(y_values)} dependencies={dependency_state}"
    )

    # ED's compatibility LoRA inputs return real axis objects rather than
    # plain lists.  Re-tag those axes so the ED sampler owns model loading and
    # never falls through to the non-LoRA grid path.
    if x_type in LEGACY_LORA_TYPES and any(isinstance(value, XYLoraAxisValue) for value in x_values):
        x_type = "ED_LORA_SWEEP_X"
    if y_type in LEGACY_LORA_TYPES and any(isinstance(value, XYLoraAxisValue) for value in y_values):
        y_type = "ED_LORA_SWEEP_Y"

    if (
        x_type != "XY_Capsule"
        and x_type == y_type
        and x_type not in {"Nothing", "Positive Prompt S/R", "Negative Prompt S/R"}
        and x_type not in ED_LORA_TYPES
    ):
        if x_type != "Nothing":
            _error("XY Plot requires different X and Y input types")
        return None

    if (
        (x_type in ENCODE_TYPES or y_type in ENCODE_TYPES)
        and x_type not in ED_LORA_TYPES
        and y_type not in ED_LORA_TYPES
        and dependencies is None
    ):
        _error("dependencies input is required for this XY Plot type")
        return None

    if (
        (x_type in LORA_PLOT_TYPES and y_type not in LORA_PLOT_TYPES and y_type != "Nothing")
        or (y_type in LORA_PLOT_TYPES and x_type not in LORA_PLOT_TYPES and x_type != "Nothing")
    ):
        _error("both X and Y must be connected for the LoRA Plot mode")
        return None

    # Keep the old labels and value cleanup so saved workflows remain valid.
    if x_type == "Sampler" and y_type == "Scheduler":
        x_values = [(item[0], "") for item in x_values]
    elif y_type == "Sampler" and x_type == "Scheduler":
        y_values = [(item[0], "") for item in y_values]
    if x_type == "Scheduler" and y_type != "Sampler":
        x_values = [(item, None) for item in x_values]
    if y_type == "Scheduler" and x_type != "Sampler":
        y_values = [(item, None) for item in y_values]
    if x_type == "Checkpoint" and y_type == "VAE":
        x_values = [(item[0], item[1], None) for item in x_values]
    elif y_type == "Checkpoint" and x_type == "VAE":
        y_values = [(item[0], item[1], None) for item in y_values]

    if str(xy_flip) == "True":
        x_type, y_type = y_type, x_type
        x_values, y_values = y_values, x_values

    return {
        "xyplot": (
            x_type, x_values, y_type, y_values, int(grid_spacing),
            str(y_label_orientation), str(cache_models) == "True",
            str(ksampler_output_image) == "Plot", my_unique_id, dependencies,
        )
    }


class EDXYPlot:
    """ED replacement for the legacy ``XY Plot`` node."""

    @classmethod
    def INPUT_TYPES(cls):
        # Import ComfyUI's model registry only when node metadata is queried;
        # pure script-composition tests remain independent of the runtime.
        return {
            "required": {
                "grid_spacing": ("INT", {"default": 0, "min": 0, "max": 500, "step": 5}),
                "XY_flip": (["False", "True"],),
                "Y_label_orientation": (["Horizontal", "Vertical"], {"default": "Vertical"}),
                "cache_models": (["True", "False"],),
                "ksampler_output_image": (["Images", "Plot"],),
            },
            "optional": {
                "dependencies": ("DEPENDENCIES",),
                "X": ("XY",),
                "Y": ("XY",),
            },
            "hidden": {"my_unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("SCRIPT",)
    RETURN_NAMES = ("SCRIPT",)
    FUNCTION = "XYplot"
    CATEGORY = "Efficiency Nodes/Scripts"

    def XYplot(self, grid_spacing, XY_flip, Y_label_orientation, cache_models,
               ksampler_output_image, my_unique_id, dependencies=None, X=None, Y=None):
        return (compose_xyplot_script(
            grid_spacing, XY_flip, Y_label_orientation, cache_models,
            ksampler_output_image, my_unique_id, dependencies, X, Y,
        ),)


__all__ = ["EDXYPlot", "compose_xyplot_script"]
