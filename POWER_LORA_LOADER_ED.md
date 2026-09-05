# Power Lora Loader ED（LORA_STACK）

ED 版本使用 ComfyUI 核心 LoRA 加载接口，不依赖 rgthree。每个 `lora_N` 行序列化为：

```text
{ on: true/false, lora: "相对模型路径", strength: 模型强度, strengthTwo: CLIP 强度 }
```

节点内每行右侧同时显示两个数值控件：`Strength`（模型）和 `Clip`（文本编码器）。点击数值中部可输入精确值，点击两侧的 −/+ 可按 0.05 调整；左侧开关控制该行是否加入堆栈。`strengthTwo` 为空时后端使用模型强度作为兼容默认值。

`Add Lora` 使用节点内 LiteGraph 控件和 `/object_info` 的 LoRA 列表，不创建页面级浮动控件。保存/重载工作流时只恢复 LoRA 行，旧版 rgthree 的 header、divider 等占位值会被安全忽略。若 rgthree 同时启用，ED 前端不会重复创建行，并请求其显示 Model/Clip 双强度；禁用 rgthree 后由 ED 自己提供完整界面。

后端日志示例：

```text
[ED-CORE] Power Loader stack count=...: [...]
[ED-CORE] Power Loader fingerprint=...; available rows=...; external plugin dependency: none
```
