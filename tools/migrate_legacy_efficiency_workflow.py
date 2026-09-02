"""Create a non-destructive ED-compatible copy of a legacy Efficiency workflow.

Only the legacy three-node core pipeline is transformed here.  Unsupported
legacy nodes remain unchanged and are reported, so a migration never creates a
workflow that silently changes image-generation behavior.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


TYPE_MAP = {
    "Efficient Loader": "Efficient Loader 💬ED (Legacy Compat)",
    "KSampler (Efficient)": "KSampler (Efficient) 💬ED (Legacy Compat)",
    "XY Plot": "XY Plot 💬ED (Legacy Compat)",
}
KNOWN_LEGACY_TYPES = {
    "Efficient Loader", "KSampler (Efficient)", "KSampler Adv. (Efficient)", "KSampler SDXL (Eff.)",
    "Eff. Loader SDXL", "XY Plot", "XY Input: LoRA", "XY Input: LoRA Plot", "XY Input: Aesthetic Score",
    "XY Input: VAE", "XY Input: Prompt S/R", "XY Input: Checkpoint", "XY Input: Clip Skip",
}


def _legacy_loader_widgets(values: list[Any]) -> list[Any]:
    """Normalize the historical 8-widget Loader layout to the current adapter."""
    if len(values) >= 13:
        return values
    if len(values) < 8:
        raise ValueError(f"legacy Efficient Loader has {len(values)} widgets; expected at least 8")
    ckpt, vae, clip_skip, positive, negative, width, height, batch_size = values[:8]
    return [
        ckpt, vae, clip_skip, "None", 1.0, 1.0, positive, negative,
        "none", "comfy", width, height, batch_size,
    ]


def _legacy_sampler_widgets(values: list[Any]) -> list[Any]:
    """Normalize the historical Script-mode sampler widget layout."""
    if values and isinstance(values[0], str) and values[0] in {"Script", "KSampler"}:
        if len(values) < 9:
            raise ValueError(f"historical KSampler (Efficient) has {len(values)} widgets; expected at least 9")
        return [values[2], values[4], values[5], values[6], values[7], values[8], "none", "false"]
    if len(values) >= 8:
        return values[:8]
    raise ValueError(f"legacy KSampler (Efficient) has {len(values)} widgets; expected at least 8")


def _legacy_xy_widgets(values: list[Any]) -> list[Any]:
    """Normalize the historical free-text XY Plot to the ED compatibility node."""
    if len(values) < 6:
        raise ValueError(f"legacy XY Plot has {len(values)} widgets; expected at least 6")
    x_type, x_values, y_type, y_values, spacing, flip = values[:6]
    return [x_type, x_values, y_type, y_values, spacing, flip, "Vertical", "Images"]


def migrate_document(document: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Return migrated document, changed node messages, and unsupported-node messages."""
    migrated = copy.deepcopy(document)
    changed: list[str] = []
    unsupported: list[str] = []
    nodes = migrated.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("workflow JSON has no nodes array")
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        if node_type not in TYPE_MAP:
            if node_type in KNOWN_LEGACY_TYPES:
                unsupported.append(f"node {node.get('id')}: {node_type}")
            continue
        values = list(node.get("widgets_values") or [])
        if node_type == "Efficient Loader":
            node["widgets_values"] = _legacy_loader_widgets(values)
        elif node_type == "KSampler (Efficient)":
            node["widgets_values"] = _legacy_sampler_widgets(values)
        elif node_type == "XY Plot":
            node["widgets_values"] = _legacy_xy_widgets(values)
        node["type"] = TYPE_MAP[node_type]
        properties = node.get("properties")
        if isinstance(properties, dict) and properties.get("Node name for S&R") == node_type:
            properties["Node name for S&R"] = TYPE_MAP[node_type]
        changed.append(f"node {node.get('id')}: {node_type} -> {TYPE_MAP[node_type]}")
    return migrated, changed, unsupported


def _default_output(source: Path) -> Path:
    return source.with_name(f"{source.stem}_ED_migrated{source.suffix}")


def main() -> int:
    # Some Windows launchers still expose a GBK console. Keep migration logs
    # printable even though ED node display names contain emoji.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="legacy workflow JSON")
    parser.add_argument("--output", type=Path, help="new workflow path; never overwrites source")
    parser.add_argument("--write", action="store_true", help="write the migrated copy; default is dry-run")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"source workflow does not exist: {source}")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid workflow JSON: {exc}") from exc
    migrated, changed, unsupported = migrate_document(document)
    print(f"[ED-MIGRATE] source={source}")
    for message in changed:
        print(f"[ED-MIGRATE] {message}")
    for message in unsupported:
        print(f"[ED-MIGRATE] unsupported: {message}")
    if not changed:
        print("[ED-MIGRATE] no supported legacy Efficiency nodes found")
        return 0
    if unsupported:
        print("[ED-MIGRATE] refusing to write while unsupported legacy nodes remain")
        return 2
    if not args.write:
        print("[ED-MIGRATE] dry-run only; pass --write to create a new workflow file")
        return 0
    output = (args.output or _default_output(source)).resolve()
    if output == source:
        raise SystemExit("output must be different from source")
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing workflow: {output}")
    output.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ED-MIGRATE] wrote={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
