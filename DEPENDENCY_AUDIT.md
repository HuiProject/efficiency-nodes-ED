# efficiency-nodes-ED 依赖审计

## 目标

ED 的核心 Loader、LoRA Stack、XY Sweep 和缓存工具必须能够在没有其他 custom node 的情况下导入。外部节点只允许作为明确的可选适配器，不得自动安装、修改或导入其他插件源码。

## 已迁移

- `core/tsc_utils.py`：从旧工具包迁入 ED 自有副本，主模块改为相对导入。
- `Power Lora Loader 💬ED (LORA_STACK)`：改为直接使用 ComfyUI 核心 `nodes.LoraLoader`，不再继承 rgthree 类；保留原五个输出和工作流兼容名称。
- `install.py` / `uninstall.py`：仅检查或提示 ED 自身目录，不再写入其他插件目录。
- 旧版小型兼容节点（本地实现）：`Evaluate Integers`、`Evaluate Floats`、`Evaluate Strings`、
  `LoRA Stack to String converter`、`Pack SDXL Tuple`、`Unpack SDXL Tuple`、
  `Control Net Stacker`、`Apply ControlNet Stack`、`Image Overlay`。
- 旧版 `LoRA Stacker`：已按原 50 行字段协议在 `legacy_compat_ed.py` 实现；
  `js/ed_legacy_compat_widgets.js` 负责根据 `lora_count` 隐藏未使用行。

## 当前迁移门槛

旧插件不能在本阶段直接移动或删除。259 个用户工作流中仍引用以下旧类名，且它们的
socket/context 契约尚未全部兼容：

| 旧节点 | 主要差异 | 状态 |
| --- | --- | --- |
| `Efficient Loader` | 旧版返回 `MODEL, CONDITIONING+, CONDITIONING-, LATENT, VAE, CLIP, DEPENDENCIES`；ED 使用 `RGTHREE_CONTEXT` 与 ED 管线 | 待独立适配器/工作流迁移 |
| `KSampler (Efficient)` | 旧版直接接 `MODEL` 和 `SCRIPT`；ED 采样器以 `RGTHREE_CONTEXT` 为入口 | 待迁移 |
| `XY Input: LoRA` | 旧版 50 行 LoRA/批处理协议；ED 使用 ED XY 计划 | 待迁移 |
| `XY Input: LoRA Plot` | 旧版依赖旧 XY 执行器；ED Sweep V2 使用不可变 Power Loader pipe | 待迁移 |
| `XY Input: Aesthetic Score` | 旧版编码到旧 sampler script | 待迁移 |
| `Evaluate *` / stack helpers | 输入输出契约明确，无第三方运行时依赖 | 已迁移 |

只有当代表工作流在 `--disable-all-custom-nodes --whitelist-custom-nodes efficiency-nodes-ED`
模式下完成加载、执行和保存/重载检查后，才允许把旧插件移动到 `PyTXTJson\\Backups`。

## 可选适配器

Impact Pack、Impact Subpack、SUPIR、TIPO、A8R8 和旧版 Efficiency KSampler 仍由旧工作流中的适配分支使用。缺失时 ED 只抛出 `[ED-OPTIONAL]` 明确错误，不再调用 ComfyUI-Manager 自动安装。后续应将这些分支逐项迁移到 `adapters/`，核心流程不依赖它们。

## 验证

使用 `I:\ComfyUI\python\python.exe` 执行：

```powershell
python.exe -m unittest discover -s ComfyUI\custom_nodes\efficiency-nodes-ED -p test_*.py
```

`test_independence.py` 防止重新引入外部工具包导入、外部安装脚本路径和 rgthree Power Loader 继承。
