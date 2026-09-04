# ED XY LoRA 图表：Sweep 与 Plot

两种节点都从 `Power Lora Loader 💬ED (LORA_STACK)` 读取 LoRA 选择列表，
并通过 `XY Plot → KSampler (Efficient) 💬ED` 生成图表；它们的**加载蓝图不同**。

| 节点 | 核心用途 | 每个格子的模型来源 | 与普通 Power Loader 的关系 |
|---|---|---|---|
| `XY Input: LoRA Sweep 💬ED` | 正常、可比较的强度扫描 | 从未加载 LoRA 的基础模型重新构建完整堆栈 | 同一堆栈与强度时，应与普通 Power Loader 一致 |
| `XY Input: LoRA Plot` | 复刻旧版“后叠加／重复加载”效果 | 从 Power Loader 已加载 LoRA 的模型继续加载目标 LoRA | 结果刻意可能与普通 LoRA 堆栈不同 |

## 1. XY Input: LoRA Sweep 💬ED（推荐做正常比较）

每一格都会：

```text
基础 MODEL / CLIP → 按原顺序加载 Power Loader 全部启用 LoRA 一次
                 → 只替换被扫描 LoRA 的强度 → 生图
```

- 适合测试 `0.5 / 0.75 / 1.0` 等强度的实际效果。
- 可用一个节点做 X、另一个节点做 Y，生成 4×4 等双 LoRA 对比。
- 扫描目标需在 Power Loader 中**开启**；允许基础强度为 `0`。
- `XY_LORA_PLAN` 是供 ED 采样器使用的内部计划输出，通常不需要连接。

## 2. XY Input: LoRA Plot（旧版后叠加）

每一格都会：

```text
基础 MODEL / CLIP → Power Loader 的已开启 LoRA
                 → 对 Plot 选中的目标 LoRA 再加载一次 → 生图
```

它的 `MStr` / `CStr` 标签只表示**第二次加载**的强度，不代表最终的总效果。

### 每个 LoRA 独立范围

- `X_batch_count` 与 `Y_batch_count` 仍是整个图表共用的列数/行数。
- 每个已添加的 LoRA 行各自拥有 `X 起`、`X 止`、`Y 起`、`Y 止` 四个强度值。
- 图表在同一归一化位置（0→1）分别插值每一行的范围，因此 `lora_count=2`
  时两个 LoRA 可以使用不同的 X/Y 起止值，但仍生成同一个矩形网格。
- 行的名称与启用开关在界面上合并为一个节点内控件；候选列表只来自已连接的
  `Power Lora Loader ED`，连接变化后会自动刷新并保留仍有效的选择。
- 旧工作流没有行级范围时，隐藏的全局 `X_first_value`、`X_last_value`、
  `Y_first_value`、`Y_last_value` 会作为兼容回退值。

目标 LoRA 在 Power Loader 中的状态：

| 状态 | 第一次（Power Loader） | 第二次（Plot） | 适合用途 |
|---|---|---|---|
| 关闭 | 不加载 | 按图表强度加载一次 | 单独观察后叠加层；本示例工作流的默认状态 |
| 开启，非 0 | 按 Power Loader 强度加载 | 再按图表强度加载 | 复刻旧版同一 LoRA 重复叠加的效果 |
| 开启，强度 0 | 不实际加载 | 按图表强度加载 | 图表同时控制 MStr/CStr 时，通常接近“关闭” |

即使目标 LoRA 关闭，Plot 也仍会叠加在**其他已开启 LoRA**的结果上，不是脱离整个堆栈的独立模型。

## 基本连线

```text
Power Loader.CONTEXT  → Efficient Loader ED.context_opt
Power Loader.LORA_PIPE → LoRA Sweep ED.lora_pipe
                     或 → LoRA Plot.lora_pipe

LoRA Sweep ED.XY_AXIS → XY Plot.X 或 XY Plot.Y
LoRA Plot.X / Y       → XY Plot.X / Y
Efficient Loader ED.DEPENDENCIES → XY Plot.dependencies
XY Plot.SCRIPT → KSampler (Efficient) ED.script
```

`LoRA Plot` 的 X 与 Y 都需要接到 `XY Plot`；通常 X 扫 Model Strength、Y 扫 Clip Strength。

## 选择建议

- 想让图表强度与 LoRA Stacker / Power Loader 的常规出图一致：用 **LoRA Sweep ED**。
- 想研究旧工作流的“额外叠一层”或同一 LoRA 的重复加载：用 **LoRA Plot**。
- 两条路径不要混用为同一个强度结论；它们产生不同图像是设计结果，不一定是错误。
