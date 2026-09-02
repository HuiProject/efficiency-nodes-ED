"""Local compatibility nodes for the small, dependency-free Efficiency Nodes API.

These nodes intentionally copy the public data contracts of the legacy plugin,
but use only ComfyUI core and ED's own utility functions.  Loader, sampler and
XY execution nodes are kept out of this module because their implementations
have stateful behavior that needs a separate migration.
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

import torch
from PIL import Image, ImageOps

import comfy.utils
import folder_paths
import nodes

try:
    from .core.tsc_utils import pil2tensor, tensor2pil
except ImportError:  # pragma: no cover - direct module loading during development
    from core.tsc_utils import pil2tensor, tensor2pil


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(expression: str, values: dict[str, Any]) -> Any:
    """Evaluate the legacy a/b/c expression without importing simpleeval."""
    tree = ast.parse(str(expression), mode="eval")

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, str)):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](visit(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len":
            if len(node.args) != 1 or node.keywords:
                raise ValueError("len() accepts exactly one positional argument")
            return len(visit(node.args[0]))
        raise ValueError(f"unsupported expression syntax: {type(node).__name__}")

    return visit(tree)


class EvaluateIntegersED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "python_expression": ("STRING", {"default": "((a + b) - c) / 2", "multiline": False}),
            "print_to_console": (["False", "True"],),
        }, "optional": {
            "a": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
            "b": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
            "c": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
        }}

    RETURN_TYPES = ("INT", "FLOAT", "STRING")
    FUNCTION = "evaluate"
    OUTPUT_NODE = True
    CATEGORY = "Efficiency Nodes/Simple Eval"

    def evaluate(self, python_expression, print_to_console, a=0, b=0, c=0):
        result = _safe_eval(python_expression, {"a": a, "b": b, "c": c})
        result = float(result) if isinstance(result, float) else int(result)
        if print_to_console == "True":
            print(f"[ED-CORE] Evaluate Integers: {python_expression} -> {result}")
        return int(result), float(result), str(result)


class EvaluateFloatsED(EvaluateIntegersED):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        inputs["optional"] = {
            "a": ("FLOAT", {"default": 0.0, "min": -3.4e38, "max": 3.4e38, "step": 0.01}),
            "b": ("FLOAT", {"default": 0.0, "min": -3.4e38, "max": 3.4e38, "step": 0.01}),
            "c": ("FLOAT", {"default": 0.0, "min": -3.4e38, "max": 3.4e38, "step": 0.01}),
        }
        return inputs


class EvaluateStringsED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "python_expression": ("STRING", {"default": "a + b + c", "multiline": False}),
            "print_to_console": (["False", "True"],),
        }, "optional": {
            "a": ("STRING", {"default": "Hello", "multiline": False}),
            "b": ("STRING", {"default": " World", "multiline": False}),
            "c": ("STRING", {"default": "!", "multiline": False}),
        }}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "evaluate"
    OUTPUT_NODE = True
    CATEGORY = "Efficiency Nodes/Simple Eval"

    def evaluate(self, python_expression, print_to_console, a="", b="", c=""):
        # String concatenation is deliberately limited to + and len().
        result = _safe_eval(python_expression, {"a": a, "b": b, "c": c})
        if print_to_console == "True":
            print(f"[ED-CORE] Evaluate Strings: {python_expression} -> {result}")
        return (str(result),)


class LoRAStackToStringED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"lora_stack": ("LORA_STACK",)}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("LoRA string",)
    FUNCTION = "convert"
    CATEGORY = "Efficiency Nodes/Misc"

    def convert(self, lora_stack):
        return (" ".join(f"<lora:{name}:{model}:{clip}>" for name, model, clip in (lora_stack or [])),)


class LoRAStackerLegacyED:
    """Compatibility implementation of the legacy 50-row LoRA Stacker."""

    MAX_LORA_COUNT = 50

    @classmethod
    def INPUT_TYPES(cls):
        loras = ["None"] + folder_paths.get_filename_list("loras")
        required = {
            "input_mode": (["simple", "advanced"],),
            "lora_count": ("INT", {"default": 3, "min": 0, "max": cls.MAX_LORA_COUNT, "step": 1}),
        }
        for index in range(1, cls.MAX_LORA_COUNT + 1):
            required[f"lora_name_{index}"] = (loras,)
            required[f"lora_wt_{index}"] = ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01})
            required[f"model_str_{index}"] = ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01})
            required[f"clip_str_{index}"] = ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01})
        return {"required": required, "optional": {"lora_stack": ("LORA_STACK",)}}

    RETURN_TYPES = ("LORA_STACK",)
    RETURN_NAMES = ("LORA_STACK",)
    FUNCTION = "lora_stacker"
    CATEGORY = "Efficiency Nodes/Stackers"

    def lora_stacker(self, input_mode, lora_count, lora_stack=None, **kwargs):
        count = max(0, min(self.MAX_LORA_COUNT, int(lora_count)))
        result = []
        for index in range(1, count + 1):
            name = kwargs.get(f"lora_name_{index}")
            if not name or name == "None":
                continue
            if input_mode == "simple":
                strength = float(kwargs.get(f"lora_wt_{index}", 1.0))
                result.append((name, strength, strength))
            else:
                result.append((
                    name,
                    float(kwargs.get(f"model_str_{index}", 1.0)),
                    float(kwargs.get(f"clip_str_{index}", 1.0)),
                ))
        if lora_stack:
            result.extend(item for item in lora_stack if item and item[0] != "None")
        print(f"[ED-CORE] legacy LoRA Stacker count={count}, enabled={len(result)}")
        return (result,)

    @classmethod
    def VALIDATE_INPUTS(cls, lora_count, **kwargs):
        allowed = set(["None"] + folder_paths.get_filename_list("loras"))
        for index in range(1, max(0, min(cls.MAX_LORA_COUNT, int(lora_count))) + 1):
            name = kwargs.get(f"lora_name_{index}")
            if name not in allowed:
                return f"LoRA not found: {name}"
        return True


class PackSDXLTupleED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "base_model": ("MODEL",), "base_clip": ("CLIP",),
            "base_positive": ("CONDITIONING",), "base_negative": ("CONDITIONING",),
            "refiner_model": ("MODEL",), "refiner_clip": ("CLIP",),
            "refiner_positive": ("CONDITIONING",), "refiner_negative": ("CONDITIONING",),
        }}

    RETURN_TYPES = ("SDXL_TUPLE",)
    RETURN_NAMES = ("SDXL_TUPLE",)
    FUNCTION = "pack_sdxl_tuple"
    CATEGORY = "Efficiency Nodes/Misc"

    def pack_sdxl_tuple(self, base_model, base_clip, base_positive, base_negative,
                        refiner_model, refiner_clip, refiner_positive, refiner_negative):
        return ((base_model, base_clip, base_positive, base_negative,
                 refiner_model, refiner_clip, refiner_positive, refiner_negative),)


class UnpackSDXLTupleED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"sdxl_tuple": ("SDXL_TUPLE",)}}

    RETURN_TYPES = ("MODEL", "CLIP", "CONDITIONING", "CONDITIONING",
                    "MODEL", "CLIP", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("BASE_MODEL", "BASE_CLIP", "BASE_CONDITIONING+", "BASE_CONDITIONING-",
                    "REFINER_MODEL", "REFINER_CLIP", "REFINER_CONDITIONING+", "REFINER_CONDITIONING-")
    FUNCTION = "unpack_sdxl_tuple"
    CATEGORY = "Efficiency Nodes/Misc"

    def unpack_sdxl_tuple(self, sdxl_tuple):
        if not isinstance(sdxl_tuple, (tuple, list)) or len(sdxl_tuple) != 8:
            raise ValueError("SDXL_TUPLE must contain exactly 8 values")
        return tuple(sdxl_tuple)


class ControlNetStackerED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "control_net": ("CONTROL_NET",), "image": ("IMAGE",),
            "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
            "start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}),
            "end_percent": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.001}),
        }, "optional": {"cnet_stack": ("CONTROL_NET_STACK",)}}

    RETURN_TYPES = ("CONTROL_NET_STACK",)
    RETURN_NAMES = ("CNET_STACK",)
    FUNCTION = "control_net_stacker"
    CATEGORY = "Efficiency Nodes/Stackers"

    def control_net_stacker(self, control_net, image, strength, start_percent, end_percent, cnet_stack=None):
        stack = list(cnet_stack or [])
        stack.append((control_net, image, strength, start_percent, end_percent))
        return (stack,)


class ApplyControlNetStackED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"positive": ("CONDITIONING",), "negative": ("CONDITIONING",)},
                "optional": {"cnet_stack": ("CONTROL_NET_STACK",)}}

    RETURN_TYPES = ("CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("CONDITIONING+", "CONDITIONING-")
    FUNCTION = "apply_cnet_stack"
    CATEGORY = "Efficiency Nodes/Stackers"

    def apply_cnet_stack(self, positive, negative, cnet_stack=None):
        for control_net, image, strength, start_percent, end_percent in (cnet_stack or []):
            positive, negative = nodes.ControlNetApplyAdvanced().apply_controlnet(
                positive, negative, control_net, image, strength, start_percent, end_percent
            )[:2]
        return positive, negative


class ImageOverlayED:
    @classmethod
    def INPUT_TYPES(cls):
        max_resolution = getattr(nodes, "MAX_RESOLUTION", 16384)
        return {"required": {
            "base_image": ("IMAGE",), "overlay_image": ("IMAGE",),
            "overlay_resize": (["None", "Fit", "Resize by rescale_factor", "Resize to width & heigth"],),
            "resize_method": (["nearest-exact", "bilinear", "area"],),
            "rescale_factor": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 16.0, "step": 0.01}),
            "width": ("INT", {"default": 512, "min": 0, "max": max_resolution, "step": 1}),
            "height": ("INT", {"default": 512, "min": 0, "max": max_resolution, "step": 1}),
            "x_offset": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
            "y_offset": ("INT", {"default": 0, "min": -48000, "max": 48000, "step": 1}),
            "rotation": ("INT", {"default": 0, "min": -180, "max": 180, "step": 1}),
            "opacity": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.1}),
        }, "optional": {"optional_mask": ("MASK",)}}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_overlay_image"
    CATEGORY = "Efficiency Nodes/Image"

    def apply_overlay_image(self, base_image, overlay_image, overlay_resize, resize_method,
                            rescale_factor, width, height, x_offset, y_offset, rotation,
                            opacity, optional_mask=None):
        overlay = overlay_image[0] if overlay_image.ndim == 4 else overlay_image
        if overlay_resize != "None":
            source_h, source_w = overlay.shape[:2]
            if overlay_resize == "Fit":
                ratio = min(base_image.shape[1] / source_h, base_image.shape[2] / source_w)
                target = (max(1, round(source_w * ratio)), max(1, round(source_h * ratio)))
            elif overlay_resize == "Resize by rescale_factor":
                target = (max(1, round(source_w * rescale_factor)), max(1, round(source_h * rescale_factor)))
            else:
                target = (width, height)
            overlay = comfy.utils.common_upscale(overlay.unsqueeze(0).movedim(-1, 1), target[0], target[1], resize_method, False)[0].movedim(0, -1)
        overlay_pil = tensor2pil(overlay).convert("RGBA")
        overlay_pil.putalpha(Image.new("L", overlay_pil.size, 255))
        if optional_mask is not None:
            mask = tensor2pil(optional_mask[0] if optional_mask.ndim == 3 else optional_mask).convert("L").resize(overlay_pil.size)
            overlay_pil.putalpha(ImageOps.invert(mask))
        overlay_pil = overlay_pil.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)
        alpha = overlay_pil.getchannel("A").point(lambda value: max(0, int(value * (1.0 - opacity / 100.0))))
        overlay_pil.putalpha(alpha)
        result = []
        for image in base_image:
            base = tensor2pil(image).convert("RGBA")
            base.alpha_composite(overlay_pil, (x_offset, y_offset))
            result.append(pil2tensor(base.convert("RGB")).squeeze(0))
        return (torch.stack(result),)


NODE_CLASS_MAPPINGS = {
    "LoRA Stacker": LoRAStackerLegacyED,
    "Evaluate Integers": EvaluateIntegersED,
    "Evaluate Floats": EvaluateFloatsED,
    "Evaluate Strings": EvaluateStringsED,
    "LoRA Stack to String converter": LoRAStackToStringED,
    "Pack SDXL Tuple": PackSDXLTupleED,
    "Unpack SDXL Tuple": UnpackSDXLTupleED,
    "Control Net Stacker": ControlNetStackerED,
    "Apply ControlNet Stack": ApplyControlNetStackED,
    "Image Overlay": ImageOverlayED,
}
