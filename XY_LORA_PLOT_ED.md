# ED LoRA Plot

`XY Input: LoRA Plot` is an ED-owned two-axis composer for the historical
**post-stack overlay** behavior. Connect
`Power Lora Loader 💬ED (LORA_STACK).LORA_PIPE` to its `lora_pipe` input,
set `lora_count`, and choose rows from the connected stack. X scans model
strength (`X_first_value` → `X_last_value`); Y scans clip strength
(`Y_first_value` → `Y_last_value`). The same selected rows are applied to the
model/CLIP that Power Loader has **already** modified. This intentionally
loads the selected LoRA layer a second time and therefore differs from
`XY Input: LoRA Sweep 💬ED`.

The selector can include disabled Power Loader rows: they are not part of the
first stack application, but are valid second-layer overlay targets. It cannot
select a LoRA absent from the connected Power Loader's rows.

## Target state in Power Loader

Choose the state according to the comparison you need:

- **Disabled (the supplied workflow default):** the target is loaded only by
  Plot's second layer. Labels such as `MStr=0.5` mean the target's actual
  loaded strength is 0.5, after the other active Power Loader rows.
- **Enabled:** Power Loader applies its normal target strength first, then
  Plot applies the displayed value again. This is the strict historical
  duplicate-load / "wrong overlay" behaviour. A Power Loader strength of 0.6
  plus a displayed Plot value of 0.5 is two applications, not a total
  strength of 0.5.

The two states intentionally produce different images. The legacy overlay
sampler logs the target state through the Power Loader stack count and always
prints `mode=legacy-overlay` per generated cell.

Connect the node's `X` and `Y` outputs to the matching `XY Plot` inputs.
Connect `XY Plot.dependencies` to `Efficient Loader 💬ED.DEPENDENCIES` when
using encoded legacy axes or when retaining the loader metadata in saved
workflows. The sampler uses ED-local core APIs only; it does not import another
custom node.

## Wiring

```text
UNET/CLIP → Power Loader ED → Ext Model Input → Efficient Loader ED → KSampler ED
                  ├─ LORA_PIPE → XY Input: LoRA Plot
                  └─ CONTEXT ────────────────────────────┘
XY Input: LoRA Plot.X → XY Plot.X
XY Input: LoRA Plot.Y → XY Plot.Y
Efficient Loader ED.DEPENDENCIES → XY Plot.dependencies
XY Plot.SCRIPT → KSampler ED.script
```

The loader must receive the Power Loader context so its `context.model/clip`
already includes the first stack. Otherwise the overlay cannot reproduce the
pre-31-August output.

## `XY_LORA_PLAN`

`XY Input: LoRA Sweep 💬ED` also exposes `XY_LORA_PLAN`. It is a backend-only
execution plan containing the immutable `EDLoraPipe`, target names, normalized
batch values, and per-cell stack reconstruction. It is not an image or model
socket. The ED sampler consumes it through the `SCRIPT` output; leave the plan
socket unconnected unless another ED node explicitly accepts
`ED_XY_LORA_PLAN`.

Boundary logs use the following prefixes:

```text
[ED-XY-PLOT] stack count=... targets=... X values=... Y values=...
[ED-XY-PLOT] compose X=... Y=... dependencies=connected|missing
[XY-ED-V2] cell=(row,column) ... stack=<fingerprint>
```
