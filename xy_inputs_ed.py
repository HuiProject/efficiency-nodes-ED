"""ED-owned common XY input nodes.

These nodes preserve the legacy ``XY`` payload names used by existing
workflows, while keeping all implementation inside efficiency-nodes-ED.
"""

from __future__ import annotations


XYPLOT_LIM = 50
XYPLOT_DEF = 3


def generate_floats(batch_count, first_value, last_value):
    count = int(batch_count)
    if count <= 0:
        return []
    if count == 1:
        return [float(first_value)]
    step = (float(last_value) - float(first_value)) / (count - 1)
    return [round(float(first_value) + step * index, 3) for index in range(count)]


def generate_ints(batch_count, first_value, last_value):
    return [int(round(value)) for value in generate_floats(batch_count, first_value, last_value)]


class EDXYSeedsBatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM})}}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, batch_count):
        return (("Seeds++ Batch", list(range(int(batch_count)))),) if batch_count else (None,)


class EDXYAddReturnNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"XY_type": (["add_noise", "return_with_leftover_noise"],)}}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, XY_type):
        kind = "AddNoise" if XY_type == "add_noise" else "ReturnNoise"
        return ((kind, ["enable", "disable"]),)


class EDXYSteps:
    parameters = ["steps", "start_at_step", "end_at_step", "refine_at_step"]

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "target_parameter": (cls.parameters,),
            "batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "first_step": ("INT", {"default": 10, "min": 1, "max": 10000}),
            "last_step": ("INT", {"default": 20, "min": 1, "max": 10000}),
            "first_start_step": ("INT", {"default": 0, "min": 0, "max": 10000}),
            "last_start_step": ("INT", {"default": 10, "min": 0, "max": 10000}),
            "first_end_step": ("INT", {"default": 10, "min": 0, "max": 10000}),
            "last_end_step": ("INT", {"default": 20, "min": 0, "max": 10000}),
            "first_refine_step": ("INT", {"default": 10, "min": 0, "max": 10000}),
            "last_refine_step": ("INT", {"default": 20, "min": 0, "max": 10000}),
        }}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, target_parameter, batch_count, first_step, last_step,
                 first_start_step, last_start_step, first_end_step, last_end_step,
                 first_refine_step, last_refine_step):
        ranges = {
            "steps": ("Steps", first_step, last_step),
            "start_at_step": ("StartStep", first_start_step, last_start_step),
            "end_at_step": ("EndStep", first_end_step, last_end_step),
            "refine_at_step": ("RefineStep", first_refine_step, last_refine_step),
        }
        axis_type, first, last = ranges[target_parameter]
        values = generate_ints(batch_count, first, last)
        return ((axis_type, values),) if values else (None,)


class EDXYCFG:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "first_cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0}),
            "last_cfg": ("FLOAT", {"default": 9.0, "min": 0.0, "max": 100.0}),
        }}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, batch_count, first_cfg, last_cfg):
        values = generate_floats(batch_count, first_cfg, last_cfg)
        return (("CFG Scale", values),) if values else (None,)


class EDXYSamplerScheduler:
    parameters = ["sampler", "scheduler", "sampler & scheduler"]

    @classmethod
    def INPUT_TYPES(cls):
        import comfy.samplers
        samplers = ["None"] + list(comfy.samplers.KSampler.SAMPLERS)
        schedulers = ["None"] + list(comfy.samplers.KSampler.SCHEDULERS)
        inputs = {"required": {
            "target_parameter": (cls.parameters,),
            "input_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM, "step": 1}),
        }}
        for index in range(1, XYPLOT_LIM + 1):
            inputs["required"][f"sampler_{index}"] = (samplers,)
            inputs["required"][f"scheduler_{index}"] = (schedulers,)
        return inputs

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, target_parameter, input_count, **kwargs):
        count = max(0, min(int(input_count), XYPLOT_LIM))
        if target_parameter == "scheduler":
            values = [kwargs.get(f"scheduler_{index}") for index in range(1, count + 1)]
            values = [value for value in values if value and value != "None"]
            return (("Scheduler", values),) if values else (None,)
        samplers = [kwargs.get(f"sampler_{index}") for index in range(1, count + 1)]
        schedulers = [kwargs.get(f"scheduler_{index}") for index in range(1, count + 1)]
        if target_parameter == "sampler":
            values = [(sampler, None) for sampler in samplers if sampler and sampler != "None"]
        else:
            values = [
                (sampler, scheduler if scheduler and scheduler != "None" else None)
                for sampler, scheduler in zip(samplers, schedulers)
                if sampler and sampler != "None"
            ]
        return (("Sampler", values),) if values else (None,)


class EDXYDenoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "batch_count": ("INT", {"default": XYPLOT_DEF, "min": 0, "max": XYPLOT_LIM}),
            "first_denoise": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "last_denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
        }}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, batch_count, first_denoise, last_denoise):
        values = generate_floats(batch_count, first_denoise, last_denoise)
        return (("Denoise", values),) if values else (None,)


class EDXYJoinInputs:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"XY_1": ("XY",), "XY_2": ("XY",)}}

    RETURN_TYPES = ("XY",)
    RETURN_NAMES = ("X or Y",)
    FUNCTION = "xy_value"
    CATEGORY = "Efficiency Nodes/XY Inputs"

    def xy_value(self, XY_1, XY_2):
        if not XY_1:
            return (XY_2,)
        if not XY_2:
            return (XY_1,)
        type_1, values_1 = XY_1
        type_2, values_2 = XY_2
        if type_1 != type_2:
            raise ValueError("Join XY Inputs requires matching axis types")
        if type_1 == "Seeds++ Batch":
            values = list(range(len(values_1) + len(values_2)))
        else:
            values = list(values_1) + list(values_2)
        return ((type_1, values),)


NODE_CLASS_MAPPINGS = {
    "XY Input: Seeds++ Batch": EDXYSeedsBatch,
    "XY Input: Add/Return Noise": EDXYAddReturnNoise,
    "XY Input: Steps": EDXYSteps,
    "XY Input: CFG Scale": EDXYCFG,
    "XY Input: Sampler/Scheduler": EDXYSamplerScheduler,
    "XY Input: Denoise": EDXYDenoise,
    "Join XY Inputs of Same Type": EDXYJoinInputs,
}

