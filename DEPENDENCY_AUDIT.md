# efficiency-nodes-ED 依赖审计

## 目标

ED 的核心 Loader、LoRA Stack、XY Sweep 和缓存工具必须能够在没有其他 custom node 的情况下导入。外部节点只允许作为明确的可选适配器，不得自动安装、修改或导入其他插件源码。

## 已迁移

- `core/tsc_utils.py`：从旧工具包迁入 ED 自有副本，主模块改为相对导入。
- `Power Lora Loader 💬ED (LORA_STACK)`：改为直接使用 ComfyUI 核心 `nodes.LoraLoader`，不再继承 rgthree 类；保留原五个输出和工作流兼容名称。
- `install.py` / `uninstall.py`：仅检查或提示 ED 自身目录，不再写入其他插件目录。

## 可选适配器

Impact Pack、Impact Subpack、SUPIR、TIPO、A8R8 和旧版 Efficiency KSampler 仍由旧工作流中的适配分支使用。缺失时 ED 只抛出 `[ED-OPTIONAL]` 明确错误，不再调用 ComfyUI-Manager 自动安装。后续应将这些分支逐项迁移到 `adapters/`，核心流程不依赖它们。

## 验证

使用 `I:\ComfyUI\python\python.exe` 执行：

```powershell
python.exe -m unittest discover -s ComfyUI\custom_nodes\efficiency-nodes-ED -p test_*.py
```

`test_independence.py` 防止重新引入外部工具包导入、外部安装脚本路径和 rgthree Power Loader 继承。
