"""ED 卸载检查：不会触碰其他插件或 ComfyUI 前端文件。"""
from pathlib import Path

def main() -> int:
    root = Path(__file__).resolve().parent
    print(f"[ED-UNINSTALL] 请由插件管理器移除目录：{root}")
    print("[ED-UNINSTALL] 未修改任何外部 custom_nodes 文件。")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
