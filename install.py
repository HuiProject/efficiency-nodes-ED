"""ED 安装入口：只检查自身文件，不修改其他 custom_nodes。"""
from pathlib import Path

def main() -> int:
    root = Path(__file__).resolve().parent
    required = [root / "__init__.py", root / "efficiency_nodes_ED.py", root / "core" / "tsc_utils.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("[ED-INSTALL] 缺少 ED 自带文件:\n" + "\n".join(missing))
        return 1
    print("[ED-INSTALL] 独立模式就绪：仅使用 efficiency-nodes-ED 自身文件。")
    print("[ED-INSTALL] 不会修改 efficiency-nodes-comfyui、rgthree-comfy 或 Impact Pack。")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
