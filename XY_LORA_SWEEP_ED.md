# ED LoRA Sweep

`XY Input: LoRA Sweep 💬ED` is the **consistent immutable-stack** XY path.
It is intentionally different from `XY Input: LoRA Plot`.

The node reads `Power Lora Loader 💬ED (LORA_STACK).LORA_PIPE`, records the
ordered base stack, and creates a plan. For every XY cell, the sampler starts
again from `lora_pipe.base_model/base_clip`, applies the entire stack exactly
once, and replaces only the selected rows' strengths. The same stack and seed
therefore match a normal Power Loader run at equivalent strengths.

## Wiring

```text
Power Loader ED.LORA_PIPE → LoRA Sweep ED.lora_pipe
LoRA Sweep ED.XY_AXIS → XY Plot.X or XY Plot.Y
XY Plot.SCRIPT → KSampler ED.script
Power Loader ED.CONTEXT → Efficient Loader ED.context_opt → KSampler ED.context
```

Use one Sweep node for X and another for Y to make a 4×4 grid. The `axis`
selector is explicit: `X Model`, `X Clip`, `Y Model`, `Y Clip`, `X Model and
Clip`, or `Y Model and Clip`. The first word chooses the grid direction and
the remaining words choose whether Model, CLIP, or both strengths are swept.
The legacy values `X` and `Y` remain accepted as aliases for `X Model` and
`Y Clip`.
Each node has its own selected rows/ranges and its `batch_count` is shared by
all rows in that node. Targets must be enabled in the actual `lora_pipe` (an
enabled target may have strength `0`, allowing a zero-to-positive sweep).

Each selected row stores six values (the selector/toggle plus two ranges):

```text
scan_lora_name_N
scan_lora_N_toggle
scan_lora_first_strength_N       # Model 起
scan_lora_last_strength_N        # Model 止
scan_lora_clip_first_strength_N  # CLIP 起
scan_lora_clip_last_strength_N   # CLIP 止
```

The frontend renders four independent native number widgets: `Model S`,
`Model E`, `Clip S`, and `Clip E` (`S` = Start, `E` = End). Keeping Start and
End separate preserves reliable mouse focus and direct editing on ComfyUI
0.30.2. The inactive range is hidden according to `axis`; both ranges are
shown only for the `Model and Clip` modes.

Old four-value rows are still accepted. Their CLIP range is initialized from
the Model range, so existing workflows keep their previous output until the
new CLIP controls are edited. Plot-style `scan_lora_y_*` aliases are also
accepted when present in an early migration save.

Each row's LoRA selector is a single node-owned bar combining the Power
Loader-style enable toggle and dropdown. Existing saved combo/toggle rows are
upgraded to this same bar when the workflow opens; the serialized backend
fields remain `scan_lora_name_N` and `scan_lora_N_toggle` for compatibility.

## Outputs

- `SCRIPT`: direct one-axis execution plan for a KSampler ED script input.
- `XY_LORA_PLAN`: an internal backend plan (`EDLoraSweepPlan`). It owns the
  immutable pipe, target rows and cell reconstruction rules. Usually leave it
  unconnected; it is not an image/model output.
- `XY_AXIS`: connect this to `XY Plot.X` or `.Y` for a grid.

Relevant runtime log entries:

```text
[XY-ED-STACKER] count=... enabled_rows=...
[XY-ED-V2] plan targets=... axis_mode=model/clip model_ranges=... clip_ranges=...
[XY-ED-V2] cell=(row,column) ... mode=immutable
```

`CStr` only affects LoRAs that contain text-encoder/CLIP weights. Many Anima
LoRAs contain UNet-only weights; for those files changing CLIP strength is
correctly a no-op, while the same control works on a LoRA that includes CLIP
weights.
