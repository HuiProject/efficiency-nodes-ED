# ED LoRA Plot

`XY Input: LoRA Plot` is an ED-owned axis-profile composer for the historical
**post-stack overlay** behavior. Connect
`Power Lora Loader 💬ED (LORA_STACK).LORA_PIPE` to its `lora_pipe` input,
set `lora_count`, and choose rows from the connected stack. `batch_count` is
the single scan dimension; `axis` chooses whether its cells are sent to X or Y.
Each selected row has its own Model and Clip range controls. The `axis` selector uses the same six options as
LoRA Sweep: `X Model`, `X Clip`, `Y Model`, `Y Clip`, `X Model and Clip`, and
`Y Model and Clip`. The selected direction is scanned as one axis;
`Model and Clip` changes both weights together. The
new Model/Clip range controls default to `1.0`; set Start/End explicitly for a
strength sweep.
same selected rows are applied to the model/CLIP that Power Loader has
**already** modified. This intentionally loads the selected LoRA layer a
second time and therefore differs from `XY Input: LoRA Sweep 💬ED`.

There are no hidden global range or second batch widgets. Every active row
serializes its explicit Model/Clip start and end values.

The visible range controls are compact paired bars: `Model S/E` and `Clip S/E`
(`S` = Start, `E` = End). The active range is shown according to `axis`; the
inactive range is hidden to keep the node compact. The serialized backend names
still use `scan_lora_*` for the active dynamic rows; that implementation name is
not shown in the node UI.

The selector can include disabled Power Loader rows: they are not part of the
first stack application, but are valid second-layer overlay targets. It cannot
select a LoRA absent from the connected Power Loader's rows. The selector is a
node-owned LiteGraph widget, so the selected value persists in the workflow;
it is not a page-level floating menu.

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

Connect the node's single `XY_AXIS` output to the matching `XY Plot.X` or
`XY Plot.Y` input selected by `axis`. With `lora_count=2`, both rows are applied
at every cell, each using its own four range values; the node does not create a
permanently tall set of unused rows.
Connect `XY Plot.dependencies` to `Efficient Loader 💬ED.DEPENDENCIES` when
using encoded legacy axes or when retaining the loader metadata in saved
workflows. The sampler uses ED-local core APIs only; it does not import another
custom node.

## Wiring

```text
UNET/CLIP → Power Loader ED → Ext Model Input → Efficient Loader ED → KSampler ED
                  ├─ LORA_PIPE → XY Input: LoRA Plot
                  └─ CONTEXT ────────────────────────────┘
XY Input: LoRA Plot.XY_AXIS → XY Plot.X or XY Plot.Y
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
[ED-XY-PLOT] stack count=... rows=... axis=... values=...
[ED-XY-PLOT] compose X=... Y=... dependencies=connected|missing
[XY-ED-V2] cell=(row,column) ... stack=<fingerprint>
```
