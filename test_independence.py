"""ED 独立性回归检查。使用 ComfyUI 内部 Python 运行：python.exe test_independence.py"""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
FORBIDDEN_PATHS = ("efficiency-nodes-comfyui", "rgthree-comfy", "ComfyUI-Impact-Pack")


def test_no_external_python_imports():
    """核心 Python 不得通过路径导入其他 custom_nodes。"""
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert "from tsc_utils import" not in text, path
        assert "sys.path.append(efficiency_nodes_dir)" not in text, path


def test_install_scripts_are_local_only():
    for name in ("install.py", "uninstall.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "../" not in text, f"{name}: 外部相对路径引用"


def test_power_loader_does_not_resolve_rgthree():
    text = (ROOT / "efficiency_nodes_ED.py").read_text(encoding="utf-8")
    assert "NODES.get(\"Power Lora Loader (rgthree)\")" not in text
    tree = ast.parse(text)
    assert tree is not None


if __name__ == "__main__":
    import unittest
    unittest.main()
