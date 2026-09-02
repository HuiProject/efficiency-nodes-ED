"""Inventory legacy efficiency-nodes references in ComfyUI workflow JSON.

The inventory is read-only.  It understands both the canvas workflow format
(``nodes``/``type``) and API prompt format (``class_type``), records parse
failures instead of aborting, and emits a compact Markdown migration report.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


LEGACY_TYPES = (
    "Efficient Loader",
    "Eff. Loader SDXL",
    "KSampler (Efficient)",
    "KSampler Adv. (Efficient)",
    "KSampler SDXL (Eff.)",
    "XY Plot",
    "XY Input: LoRA",
    "XY Input: LoRA Plot",
    "XY Input: LoRA Stacks",
    "XY Input: Aesthetic Score",
)


def _nodes_from_document(document):
    if isinstance(document, dict) and isinstance(document.get("nodes"), list):
        return document["nodes"]
    if isinstance(document, dict):
        # API-format prompts map node ids to {class_type, inputs} objects.
        return [dict(value, id=key) for key, value in document.items()
                if isinstance(value, dict) and "class_type" in value]
    return []


def _node_type(node):
    if not isinstance(node, dict):
        return None
    return node.get("type") or node.get("class_type") or node.get("comfyClass")


def inventory(root: Path):
    counts = Counter()
    files_by_type = defaultdict(list)
    legacy_nodes = []
    parse_errors = []
    workflow_count = 0
    node_count = 0

    for path in sorted(root.rglob("*.json")):
        if path.name.startswith("."):
            continue
        workflow_count += 1
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # keep auditing other workflows
            parse_errors.append((path, str(exc)))
            continue
        for node in _nodes_from_document(document):
            node_type = _node_type(node)
            if not node_type:
                continue
            node_count += 1
            counts[node_type] += 1
            if node_type in LEGACY_TYPES:
                relative = str(path.relative_to(root)).replace("\\", "/")
                files_by_type[node_type].append(relative)
                legacy_nodes.append((relative, node.get("id", "?"), node_type))

    return {
        "workflow_count": workflow_count,
        "node_count": node_count,
        "counts": counts,
        "files_by_type": files_by_type,
        "legacy_nodes": legacy_nodes,
        "parse_errors": parse_errors,
    }


def render_report(result, root: Path) -> str:
    lines = [
        "# Legacy Efficiency Workflow Inventory",
        "",
        f"- Workflow JSON files scanned: **{result['workflow_count']}**",
        f"- Nodes indexed: **{result['node_count']}**",
        f"- Root: `{root}`",
        "",
        "## Legacy Node Counts",
        "",
        "| Node type | Uses | Workflows |",
        "| --- | ---: | ---: |",
    ]
    for node_type in LEGACY_TYPES:
        uses = result["counts"].get(node_type, 0)
        workflows = len(set(result["files_by_type"].get(node_type, [])))
        lines.append(f"| `{node_type}` | {uses} | {workflows} |")

    lines.extend(["", "## Migration Order", ""])
    lines.extend([
        "1. LoRA stack/XY inputs: preserve the 50-row payload and add an ED-owned",
        "   immutable stack adapter; do not read the global LoRA list when a stack",
        "   is connected.",
        "2. XY Plot script composer: keep the `xyplot` payload and migrate common",
        "   axes through the ED sampler before model/prompt-specific axes.",
        "3. Loader and sampler advanced branches: migrate only after a representative",
        "   workflow passes load, queue, save, and reload in ED-only mode.",
        "",
    ])
    if result["parse_errors"]:
        lines.extend(["## Parse Errors", ""])
        for path, error in result["parse_errors"]:
            lines.append(f"- `{path.relative_to(root)}`: `{error}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = inventory(args.workflows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(result, args.workflows), encoding="utf-8")
    print(f"[ED-AUDIT] workflows={result['workflow_count']} nodes={result['node_count']} "
          f"legacy_nodes={len(result['legacy_nodes'])} parse_errors={len(result['parse_errors'])}")
    for node_type in LEGACY_TYPES:
        count = result["counts"].get(node_type, 0)
        if count:
            print(f"[ED-AUDIT] {node_type}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
