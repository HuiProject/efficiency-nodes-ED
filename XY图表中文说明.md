# ED XY LoRA 图表：Sweep 与 Plot

两种节点都从 `Power Lora Loader ED (LORA_STACK)` 读取 LoRA 选择列表，
并通过 `XY Plot → KSampler (Efficient) 💬ED` 生成图表；它们的**加载蓝图不同**。

节点显示名称现在区分为：

- `XY Input: LoRA Sweep (ED)`：从同一份基础 LoRA 栈重建每个网格单元，适合正常强度对比。
- `XY Input: LoRA Plot (Legacy Overlay)`：在 Power Loader 已应用结果上再次叠加目标 LoRA，保留旧版后加载效果。

图表中的 LoRA 标签会在文件名之前标出来源，例如 `Sweep: shiny-skin MStr=0.5` 或
`Plot: shiny-skin MStr=0.5`；每个 LoRA 名称都会省略目录及
`.safetensors`、`.ckpt`、`.pt` 等模型扩展名，即使同一轴同时扫描多个 LoRA 也是如此。

两种 LoRA 输入节点还都提供末尾的 `LORA_NAMES` 文本输出。它只包含当前**已启用**的
LoRA 行，按节点行顺序省略目录和模型扩展名后以 ` + ` 连接，例如
`shiny-skin + style_makeup`。可将它接到文本预览节点或支持 `STRING` 文件名前缀的保存节点；
原有 `XY_AXIS`、`SCRIPT`、`XY_LORA_PLAN` 输出索引没有变化。

若扫描节点保留在工作流中但所有扫描行已关闭、未选择，或保存后目标根本不在 Power Loader 的
配置行中，它会安全退化为 `Nothing` XY 轴：Sweep 的 `SCRIPT` 原样透传，`LORA_NAMES` 为空。
因此可保留文件名/预览连线并正常生成基础单图，不会因被忽略的 XY 分支中断整个队列；日志会以
`[XY-ED-V2] inactive` 或 `[ED-XY-PLOT] inactive` 说明原因。

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
- 扫描目标可在 Power Loader 中开启，也可关闭但仍保留为该节点的一行；关闭时，Sweep 仅在
  自己的计划栈中以 `0 / 0` 加入它，不改变 Power Loader 的普通模型输出。
- `XY_LORA_PLAN` 是供 ED 采样器使用的内部计划输出，通常不需要连接。

### Sweep 与关闭目标：执行规则

| Power Loader 中的目标 | Sweep 行开关 | Sweep 输出 | `XY_AXIS → XY Plot → KSampler` | `SCRIPT → KSampler` | `LORA_NAMES` |
|---|---|---|---|---|---|
| 开启 | 开启 | 原始不可变堆栈中替换该行强度 | 正常生成带标签 XY 图表 | 正常执行单轴扫描并输出图像批次 | 目标名 |
| **关闭，但仍是 Power Loader 的一行** | **开启** | 仅在 Sweep 计划栈追加该 LoRA 的 `0 / 0` 基线；每格再按 Start/End 覆盖 | **正常生成 XY 图表** | **正常执行单轴扫描** | 目标名 |
| 任意 | 关闭、`None` 或未选择 | `Nothing` XY 轴；不建立扫描计划 | XY Plot 被视为无轴，KSampler 生成基础单图 | SCRIPT 原样透传，KSampler 生成基础单图 | 空文本 |
| 不存在于 Power Loader 配置行（旧工作流残留） | 开启 | 安全跳过为 `Nothing` XY 轴，并打印 inactive 日志 | 基础单图，不报错 | 基础单图，不报错 | 空文本 |

第二行是“关闭后仍要扫描”的推荐方式：Power Loader 保持关闭，Sweep 行保持开启并填写范围。
这样普通流程不会加载该 LoRA；只有连接到该 Sweep 的图表或 SCRIPT 采样才加载它。

## 2. XY Input: LoRA Plot（旧版后叠加）

每一格都会：

```text
基础 MODEL / CLIP → Power Loader 的已开启 LoRA
                 → 对 Plot 选中的目标 LoRA 再加载一次 → 生图
```

它的 `MStr` / `CStr` 标签只表示**第二次加载**的强度，不代表最终的总效果。

### 每个 LoRA 独立范围

- `batch_count` 是当前 Plot 轴的唯一批次数；`axis` 决定输出接到 XY Plot 的 X 或 Y。
- 每个已添加的 LoRA 行各自拥有 `Model S`、`Model E`、`Clip S`、`Clip E` 四个强度值（S=Start，E=End）。
- 每个起止值旁边都有对应的 `FLOAT` 输入插槽；连接外部数值时，以连接值覆盖节点内的滑块值，未连接时使用节点内数值。
- 图表在同一归一化位置（0→1）分别插值每一行的范围，因此 `lora_count=2`
  时两个 LoRA 可以使用不同的 X/Y 起止值，但仍生成同一个矩形网格。
- 行的名称与启用开关在界面上合并为一个节点内控件；候选列表只来自已连接的
  `Power Lora Loader ED`，连接变化后会自动刷新并保留仍有效的选择。
- 每个 Plot 节点只输出一个 `XY_AXIS`；Model/Clip 起止值按每个 LoRA 行独立保存。
  界面使用 `Model S/E`、`Clip S/E`，由 `axis` 隐藏不参与当前扫描的范围；减少 `lora_count` 时会同步移除未连接的多余插槽。

目标 LoRA 在 Power Loader 中的状态：

| 状态 | 第一次（Power Loader） | 第二次（Plot） | 适合用途 |
|---|---|---|---|
| 关闭 | 不加载 | 按图表强度加载一次 | 单独观察后叠加层；本示例工作流的默认状态 |
| 开启，非 0 | 按 Power Loader 强度加载 | 再按图表强度加载 | 复刻旧版同一 LoRA 重复叠加的效果 |
| 开启，强度 0 | 不实际加载 | 按图表强度加载 | 图表同时控制 MStr/CStr 时，通常接近“关闭” |

即使目标 LoRA 关闭，Plot 也仍会叠加在**其他已开启 LoRA**的结果上，不是脱离整个堆栈的独立模型。

## 3. XY Plot 参数

- `grid_spacing`：网格单元之间的像素间距。0 表示紧贴排列，数值越大留白越宽。
- `XY_flip`：交换 X、Y 两个方向及其标签；用于改变横纵轴布局，不改变每格的采样值。
- `Y_label_orientation`：Y 轴标签方向。`Vertical` 会顺时针旋转 90°，适合较长的 LoRA 名称；`Horizontal` 保持横向文字。
- `cache_models`：是否允许 XY 采样流程缓存已加载模型。`True` 可减少重复加载、提高速度，但会占用更多内存；显存紧张时用 `False`。
- `ksampler_output_image`：采样器输出模式：
  - `Images`：输出各网格单元组成的图像批次。
  - `Plot`：输出带 X/Y 标签的合成图表。
  - `Plot+Image`：界面同时预览合成图表和单元图像；`OUTPUT_IMAGE` 仍是单元图像批次，
    `XY_PLOT_IMAGE` 是单独的合成图表。图表尺寸通常大于单元图，不能放进同一 IMAGE 批次；
    要持久保存两者，分别将两个输出接到各自的保存节点。

## 基本连线

```text
Power Loader.CONTEXT  → Efficient Loader ED.context_opt
Power Loader.LORA_PIPE → LoRA Sweep ED.lora_pipe
                     或 → LoRA Plot.lora_pipe

LoRA Sweep ED.XY_AXIS → XY Plot.X 或 XY Plot.Y
LoRA Plot.XY_AXIS     → XY Plot.X 或 XY Plot.Y（按 axis）
Efficient Loader ED.DEPENDENCIES → XY Plot.dependencies
XY Plot.SCRIPT → KSampler (Efficient) ED.script

KSampler (Efficient) ED.OUTPUT_IMAGE  → Image Save（保存单元图像）
KSampler (Efficient) ED.XY_PLOT_IMAGE → Image Save（保存带标签图表）
```

`LoRA Plot` 只需将 `XY_AXIS` 接到一个方向；需要二维图表时，另一个方向使用独立的
Sweep 或 Plot 节点。

## 选择建议

- 想让图表强度与 LoRA Stacker / Power Loader 的常规出图一致：用 **LoRA Sweep ED**。
- 想研究旧工作流的“额外叠一层”或同一 LoRA 的重复加载：用 **LoRA Plot**。
- 两条路径不要混用为同一个强度结论；它们产生不同图像是设计结果，不一定是错误。
