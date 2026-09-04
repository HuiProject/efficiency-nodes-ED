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

Use one Sweep node for X and another for Y to make a 4×4 grid. Each node has
its own selected rows/ranges; its `batch_count` is shared by all of its rows.
Targets must be enabled in the actual `lora_pipe` (an enabled target may have
strength `0`, allowing a zero-to-positive sweep).

## Outputs

- `SCRIPT`: direct one-axis execution plan for a KSampler ED script input.
- `XY_LORA_PLAN`: an internal backend plan (`EDLoraSweepPlan`). It owns the
  immutable pipe, target rows and cell reconstruction rules. Usually leave it
  unconnected; it is not an image/model output.
- `XY_AXIS`: connect this to `XY Plot.X` or `.Y` for a grid.

Relevant runtime log entries:

```text
[XY-ED-STACKER] count=... enabled_rows=...
[XY-ED-V2] plan targets=... resolved_values=... base_stack=...
[XY-ED-V2] cell=(row,column) ... mode=immutable
```
