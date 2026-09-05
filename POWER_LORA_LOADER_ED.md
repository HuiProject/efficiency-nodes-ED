# Power Lora Loader ED（LORA_STACK）

ED 版本使用 ComfyUI 核心 LoRA 加载接口，不依赖 rgthree。每个 `lora_N` 行序列化为：

```text
{ on: true/false, lora: "相对模型路径", strength: 模型强度, strengthTwo: CLIP 强度 }
```

节点内每行右侧同时显示两个数值控件：`Strength`（模型）和 `Clip`（文本编码器）。新建行两者默认均为 `1.0`；旧工作流的空 `strengthTwo` 会迁移为该行的模型强度，保持旧行为。点击数值中部可输入精确值，点击两侧的 −/+ 可按 0.05 调整；左侧开关控制该行是否加入堆栈。

`Clip` 只有在 LoRA 文件实际包含文本编码器/CLIP 权重时才会改变图像。Anima 目录中常见的 LoRA 是 UNet/扩散模型权重，因此调节 `Clip` 后图像不变属于正常结果，并不表示控件失效。

`Add Lora` 使用节点内 LiteGraph 控件和 `/object_info` 的 LoRA 列表，不创建页面级浮动控件。保存/重载工作流时只恢复 LoRA 行，旧版 rgthree 的 header、divider 等占位值会被安全忽略。若 rgthree 同时启用，ED 前端不会重复创建行，而是在 `nodeCreated`、`configure` 和 `afterConfigureGraph` 三个边界把旧工作流的 `Show Strengths=Single Strength` 自动迁移为 `Separate Model & Clip`，并将空的 `strengthTwo` 初始化为该行的模型强度；禁用 rgthree 后由 ED 自己提供完整界面。因此无需逐个工作流手动改属性。

如果重启后仍看不到 `Clip`，请确认浏览器已重新加载 `/extensions/efficiency-nodes-ED/ed_power_lora_loader.js`（可用 Ctrl+F5），并检查浏览器控制台是否出现 `[ED-UI] Power Loader migrated...`。这属于前端缓存/扩展加载问题，不是后端 LoRA 参数缺失。

后端日志示例：

```text
[ED-CORE] Power Loader stack count=...: [...]
[ED-CORE] Power Loader fingerprint=...; available rows=...; external plugin dependency: none
```
