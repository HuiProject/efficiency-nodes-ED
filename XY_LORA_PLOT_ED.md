# ED LoRA Plot

`XY Input: LoRA Plot` is an ED-owned two-axis composer. Connect
`Power Lora Loader 💬ED (LORA_STACK).LORA_PIPE` to its `lora_pipe` input,
set `lora_count`, and choose rows from the connected stack. X scans model
strength (`X_first_value` → `X_last_value`); Y scans clip strength
(`Y_first_value` → `Y_last_value`). The same selected rows are overridden on
both axes, and the ED sampler rebuilds every cell from the immutable base
pipe.

Connect the node's `X` and `Y` outputs to the matching `XY Plot` inputs.
Connect `XY Plot.dependencies` to `Efficient Loader 💬ED.DEPENDENCIES` when
using encoded legacy axes or when retaining the loader metadata in saved
workflows. LoRA axes use the ED pipe carried by the selected rows/context;
they do not load a second model or import another custom node.

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
