"""Independent adapters for the small legacy Efficiency Nodes pipeline.

The adapters deliberately have distinct ED names.  A workflow migrator changes
old graphs to these nodes only when their socket contract is understood.  This
avoids registering a same-named node with incompatible widget serialization.
"""

from __future__ import annotations

import os

import torch
from PIL import Image, ImageDraw, ImageFont

import comfy.samplers
import folder_paths
import nodes

try:
    from .core.tsc_utils import pil2tensor, tensor2pil
except ImportError:  # pragma: no cover - direct development import
    from core.tsc_utils import pil2tensor, tensor2pil


COMMON_XY_TYPES = {"Nothing", "Seeds++ Batch", "Steps", "CFG Scale", "Sampler", "Scheduler", "Denoise"}
UNSUPPORTED_XY_TYPES = {
    "Checkpoint", "Refiner", "LoRA", "LoRA Stacks", "LoRA Batch", "LoRA Wt", "LoRA MStr", "LoRA CStr",
    "Positive Prompt S/R", "Negative Prompt S/R", "AScore+", "AScore-", "Clip Skip", "Clip Skip (Refiner)",
    "ControlNetStrength", "ControlNetStart%", "ControlNetEnd%", "AddNoise", "ReturnNoise", "StartStep",
    "EndStep", "RefineStep",
}


def _parse_semicolon_values(axis_type: str, raw_values: str):
    """Parse the legacy XY text widget into ED's stable XY payload values."""
    axis_type = str(axis_type or "Nothing")
    text = str(raw_values or "").strip().strip(";")
    if axis_type == "Nothing":
        return [""]
    if axis_type not in COMMON_XY_TYPES:
        if axis_type in UNSUPPORTED_XY_TYPES:
            raise ValueError(f"legacy XY axis is not migrated yet: {axis_type}")
        raise ValueError(f"unknown legacy XY axis: {axis_type}")
    if axis_type == "Seeds++ Batch":
        count = int(text or 0)
        return list(range(max(0, count)))
    values = [item.strip() for item in text.split(";") if item.strip()]
    if not values:
        raise ValueError(f"legacy XY axis {axis_type} requires at least one value")
    if axis_type == "Steps":
        return [max(1, int(float(value))) for value in values]
    if axis_type in {"CFG Scale", "Denoise"}:
        return [float(value) for value in values]
    if axis_type == "Scheduler":
        return values
    if axis_type == "Sampler":
        parsed = []
        for value in values:
            parts = [part.strip() for part in value.split(",")]
            parsed.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else None))
        return parsed
    return values


def build_legacy_xy_script(x_type, x_values, y_type, y_values, grid_spacing, xy_flip,
                           y_label_orientation="Vertical", ksampler_output_image="Images"):
    """Build the normal ED ``xyplot`` tuple from historical text widgets."""
    x_type = str(x_type or "Nothing")
    y_type = str(y_type or "Nothing")
    if x_type == y_type and x_type != "Nothing":
        raise ValueError("legacy XY Plot requires different X and Y axis types")
    x_payload = _parse_semicolon_values(x_type, x_values)
    y_payload = _parse_semicolon_values(y_type, y_values)
    if str(xy_flip) == "True":
        x_type, y_type, x_payload, y_payload = y_type, x_type, y_payload, x_payload
    output_mode = str(ksampler_output_image or "Images")
    output_flag = "Plot+Image" if output_mode == "Plot+Image" else output_mode == "Plot"
    return {
        "xyplot": (
            x_type, x_payload, y_type, y_payload, int(grid_spacing),
            str(y_label_orientation), False, output_flag, None, None,
        )
    }


def _apply_common_axis(axis_type, value, state):
    if axis_type == "Nothing":
        return
    if axis_type == "Seeds++ Batch":
        state["seed"] += int(value)
    elif axis_type == "Steps":
        state["steps"] = max(1, int(value))
    elif axis_type == "CFG Scale":
        state["cfg"] = float(value)
    elif axis_type == "Denoise":
        state["denoise"] = float(value)
    elif axis_type == "Scheduler":
        state["scheduler"] = str(value[0] if isinstance(value, (tuple, list)) else value)
    elif axis_type == "Sampler":
        if isinstance(value, (tuple, list)):
            state["sampler"] = str(value[0])
            if len(value) > 1 and value[1]:
                state["scheduler"] = str(value[1])
        else:
            state["sampler"] = str(value)
    else:
        raise ValueError(f"unsupported legacy XY axis: {axis_type}")


def _label(axis_type, value):
    if axis_type == "Nothing":
        return ""
    if isinstance(value, (tuple, list)):
        return f"{axis_type}={value[0]}" + (f", {value[1]}" if len(value) > 1 and value[1] else "")
    return f"{axis_type}={value}"


def _render_grid(images, x_labels, y_labels, spacing):
    """Render a minimal, dependency-free grid with clockwise Y-axis labels."""
    pil_images = [tensor2pil(image).convert("RGB") for image in images]
    columns, rows = len(x_labels), len(y_labels)
    if not pil_images or columns * rows != len(pil_images):
        raise ValueError("legacy XY grid image count does not match labels")
    cell_w, cell_h = pil_images[0].size
    font = ImageFont.load_default()
    header, gutter = 30, 60
    grid = Image.new("RGB", (gutter + columns * cell_w + max(0, columns - 1) * spacing,
                              header + rows * cell_h + max(0, rows - 1) * spacing), "white")
    draw = ImageDraw.Draw(grid)
    for index, label in enumerate(x_labels):
        draw.text((gutter + index * (cell_w + spacing) + 4, 8), label, fill="black", font=font)
    for row, label in enumerate(y_labels):
        label_image = Image.new("RGBA", (max(1, cell_h), header), (255, 255, 255, 0))
        ImageDraw.Draw(label_image).text((2, 8), label, fill="black", font=font)
        label_image = label_image.rotate(-90, expand=True)
        label_y = header + row * (cell_h + spacing) + max(0, (cell_h - label_image.height) // 2)
        grid.paste(label_image.convert("RGB"), (4, label_y))
        for column in range(columns):
            grid.paste(pil_images[row * columns + column],
                       (gutter + column * (cell_w + spacing), header + row * (cell_h + spacing)))
    return pil2tensor(grid)


class LegacyEfficientLoaderED:
    """Core-only version of the legacy Loader's public socket contract."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "ckpt_name": (folder_paths.get_filename_list("checkpoints"),),
            "vae_name": (["Baked VAE"] + folder_paths.get_filename_list("vae"),),
            "clip_skip": ("INT", {"default": -1, "min": -24, "max": 0, "step": 1}),
            "lora_name": (["None"] + folder_paths.get_filename_list("loras"),),
            "lora_model_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "lora_clip_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
            "positive": ("STRING", {"default": "CLIP_POSITIVE", "multiline": True}),
            "negative": ("STRING", {"default": "CLIP_NEGATIVE", "multiline": True}),
            "token_normalization": (["none", "mean", "length", "length+mean"],),
            "weight_interpretation": (["comfy", "A1111", "compel", "comfy++", "down_weight"],),
            "empty_latent_width": ("INT", {"default": 512, "min": 64, "max": nodes.MAX_RESOLUTION, "step": 64}),
            "empty_latent_height": ("INT", {"default": 512, "min": 64, "max": nodes.MAX_RESOLUTION, "step": 64}),
            "batch_size": ("INT", {"default": 1, "min": 1, "max": 262144}),
        }, "optional": {"lora_stack": ("LORA_STACK",), "cnet_stack": ("CONTROL_NET_STACK",)}}

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "LATENT", "VAE", "CLIP", "DEPENDENCIES")
    RETURN_NAMES = ("MODEL", "CONDITIONING+", "CONDITIONING-", "LATENT", "VAE", "CLIP", "DEPENDENCIES")
    FUNCTION = "efficientloader"
    CATEGORY = "Efficiency Nodes/Legacy Compatibility"

    def efficientloader(self, ckpt_name, vae_name, clip_skip, lora_name, lora_model_strength,
                        lora_clip_strength, positive, negative, token_normalization, weight_interpretation,
                        empty_latent_width, empty_latent_height, batch_size, lora_stack=None, cnet_stack=None):
        if token_normalization != "none" or weight_interpretation != "comfy":
            raise ValueError(
                "Legacy Loader ED only supports token_normalization=none and weight_interpretation=comfy. "
                "Use an explicit advanced text encoder for the other legacy modes."
            )
        model, clip, baked_vae = nodes.CheckpointLoaderSimple().load_checkpoint(ckpt_name)
        if vae_name != "Baked VAE":
            vae = nodes.VAELoader().load_vae(vae_name)[0]
        else:
            vae = baked_vae
        if int(clip_skip) != 0:
            clip = nodes.CLIPSetLastLayer().set_last_layer(clip, int(clip_skip))[0]
        stack = []
        if lora_name and lora_name != "None":
            stack.append((lora_name, float(lora_model_strength), float(lora_clip_strength)))
        stack.extend((name, float(model_strength), float(clip_strength))
                     for name, model_strength, clip_strength in (lora_stack or []) if name != "None")
        for name, model_strength, clip_strength in stack:
            model, clip = nodes.LoraLoader().load_lora(model, clip, name, model_strength, clip_strength)
        positive_encoded = nodes.CLIPTextEncode().encode(clip, positive)[0]
        negative_encoded = nodes.CLIPTextEncode().encode(clip, negative)[0]
        for control_net, image, strength, start_percent, end_percent in (cnet_stack or []):
            positive_encoded, negative_encoded = nodes.ControlNetApplyAdvanced().apply_controlnet(
                positive_encoded, negative_encoded, control_net, image, strength, start_percent, end_percent
            )[:2]
        latent = nodes.EmptyLatentImage().generate(empty_latent_width, empty_latent_height, batch_size)[0]
        dependencies = {
            "contract": "ed-legacy-loader-v1", "ckpt_name": ckpt_name, "vae_name": vae_name,
            "clip_skip": int(clip_skip), "positive": positive, "negative": negative, "lora_stack": stack,
        }
        print(f"[ED-LEGACY] loader ckpt={ckpt_name}, loras={len(stack)}, size={empty_latent_width}x{empty_latent_height}")
        return model, positive_encoded, negative_encoded, latent, vae, clip, dependencies


class LegacyXYPlotED:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "X_type": (sorted(COMMON_XY_TYPES),),
            "X_values": ("STRING", {"default": "", "multiline": False}),
            "Y_type": (sorted(COMMON_XY_TYPES),),
            "Y_values": ("STRING", {"default": "", "multiline": False}),
            "grid_spacing": ("INT", {"default": 0, "min": 0, "max": 500, "step": 5}),
            "XY_flip": (["False", "True"],),
            "Y_label_orientation": (["Vertical"],),
            "ksampler_output_image": (["Images", "Plot", "Plot+Image"],),
        }}

    RETURN_TYPES = ("SCRIPT",)
    RETURN_NAMES = ("SCRIPT",)
    FUNCTION = "XYplot"
    CATEGORY = "Efficiency Nodes/Legacy Compatibility"

    def XYplot(self, X_type, X_values, Y_type, Y_values, grid_spacing, XY_flip,
               Y_label_orientation="Vertical", ksampler_output_image="Images"):
        script = build_legacy_xy_script(
            X_type, X_values, Y_type, Y_values, grid_spacing, XY_flip,
            Y_label_orientation, ksampler_output_image,
        )
        print(f"[ED-LEGACY] XY axes X={X_type}, Y={Y_type}")
        return (script,)


class LegacyKSamplerED:
    EMPTY_IMAGE = torch.zeros((1, 1, 1, 3), dtype=torch.float32)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",), "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
            "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0}),
            "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
            "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
            "positive": ("CONDITIONING",), "negative": ("CONDITIONING",), "latent_image": ("LATENT",),
            "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            "preview_method": (["auto", "latent2rgb", "taesd", "vae_decoded_only", "none"],),
            "vae_decode": (["true", "true (tiled)", "false"],),
        }, "optional": {"optional_vae": ("VAE",), "script": ("SCRIPT",)}}

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "LATENT", "VAE", "IMAGE")
    RETURN_NAMES = ("MODEL", "CONDITIONING+", "CONDITIONING-", "LATENT", "VAE", "IMAGE")
    OUTPUT_NODE = True
    FUNCTION = "sample"
    CATEGORY = "Efficiency Nodes/Legacy Compatibility"

    @staticmethod
    def _decode(vae, latent, vae_decode):
        if vae is None or vae_decode == "false":
            return LegacyKSamplerED.EMPTY_IMAGE
        if vae_decode == "true (tiled)":
            return nodes.VAEDecodeTiled().decode(vae, latent, 320)[0]
        return nodes.VAEDecode().decode(vae, latent)[0]

    @staticmethod
    def _run_xy(model, positive, negative, latent_image, vae, seed, steps, cfg,
                sampler_name, scheduler, denoise, vae_decode, xy):
        x_type, x_values, y_type, y_values = xy[:4]
        if x_type not in COMMON_XY_TYPES or y_type not in COMMON_XY_TYPES:
            raise ValueError(f"Legacy KSampler ED cannot execute XY axes: {x_type}, {y_type}")
        x_values = list(x_values or [""]) if x_type != "Nothing" else [""]
        y_values = list(y_values or [""]) if y_type != "Nothing" else [""]
        images, latents = [], []
        for row, y_value in enumerate(y_values, 1):
            for column, x_value in enumerate(x_values, 1):
                state = {"seed": int(seed), "steps": int(steps), "cfg": float(cfg),
                         "sampler": sampler_name, "scheduler": scheduler, "denoise": float(denoise)}
                _apply_common_axis(x_type, x_value, state)
                _apply_common_axis(y_type, y_value, state)
                sample = nodes.KSampler().sample(
                    model, state["seed"], state["steps"], state["cfg"], state["sampler"], state["scheduler"],
                    positive, negative, latent_image, denoise=state["denoise"],
                )[0]
                latents.append(sample)
                if vae is not None:
                    images.append(LegacyKSamplerED._decode(vae, sample, vae_decode))
                print(f"[ED-LEGACY] xy cell=({row},{column}) seed={state['seed']} steps={state['steps']} cfg={state['cfg']:.6g}")
        latent_batch = dict(latents[0])
        latent_batch["samples"] = torch.cat([item["samples"] for item in latents], dim=0)
        if vae is None or vae_decode == "false":
            image_output = LegacyKSamplerED.EMPTY_IMAGE
        else:
            decoded = torch.cat(images, dim=0)
            image_output = _render_grid(images, [_label(x_type, value) for value in x_values],
                                        [_label(y_type, value) for value in y_values], int(xy[4])) if xy[7] else decoded
        return latent_batch, image_output

    def sample(self, model, seed, steps, cfg, sampler_name, scheduler, positive, negative, latent_image,
               denoise, preview_method, vae_decode, optional_vae=None, script=None):
        if script:
            unsupported = set(script) - {"xyplot"}
            if unsupported:
                raise ValueError("Legacy KSampler ED cannot execute legacy script keys: " + ", ".join(sorted(unsupported)))
        if script and script.get("xyplot"):
            if optional_vae is None:
                raise ValueError("Legacy XY Plot requires optional_vae")
            latent, image = self._run_xy(model, positive, negative, latent_image, optional_vae, seed, steps, cfg,
                                         sampler_name, scheduler, denoise, vae_decode, script["xyplot"])
        else:
            latent = nodes.KSampler().sample(model, seed, steps, cfg, sampler_name, scheduler,
                                              positive, negative, latent_image, denoise=denoise)[0]
            image = self._decode(optional_vae, latent, vae_decode)
        print(f"[ED-LEGACY] sampler seed={seed}, steps={steps}, cfg={cfg}, script={'xyplot' if script else 'none'}")
        return {"result": (model, positive, negative, latent, optional_vae, image)}


NODE_CLASS_MAPPINGS = {
    "Efficient Loader 💬ED (Legacy Compat)": LegacyEfficientLoaderED,
    "KSampler (Efficient) 💬ED (Legacy Compat)": LegacyKSamplerED,
    "XY Plot 💬ED (Legacy Compat)": LegacyXYPlotED,
}
