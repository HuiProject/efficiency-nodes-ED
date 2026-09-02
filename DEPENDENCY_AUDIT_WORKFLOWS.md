# Legacy Efficiency Workflow Inventory

- Workflow JSON files scanned: **259**
- Nodes indexed: **10113**
- Root: `I:\ComfyUI\ComfyUI\user\default\workflows`

## Legacy Node Counts

| Node type | Uses | Workflows |
| --- | ---: | ---: |
| `Efficient Loader` | 4 | 4 |
| `Eff. Loader SDXL` | 0 | 0 |
| `KSampler (Efficient)` | 4 | 4 |
| `KSampler Adv. (Efficient)` | 0 | 0 |
| `KSampler SDXL (Eff.)` | 0 | 0 |
| `XY Plot` | 23 | 17 |
| `XY Input: LoRA` | 62 | 16 |
| `XY Input: LoRA Plot` | 15 | 13 |
| `XY Input: LoRA Stacks` | 0 | 0 |
| `XY Input: Aesthetic Score` | 12 | 12 |

## Migration Order

1. LoRA stack/XY inputs: preserve the 50-row payload and add an ED-owned
   immutable stack adapter; do not read the global LoRA list when a stack
   is connected.
2. XY Plot script composer: keep the `xyplot` payload and migrate common
   axes through the ED sampler before model/prompt-specific axes.
3. Loader and sampler advanced branches: migrate only after a representative
   workflow passes load, queue, save, and reload in ED-only mode.

