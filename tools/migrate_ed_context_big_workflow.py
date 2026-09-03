"""Create an ED Context Big workflow copy with validated link ownership.

This is intentionally a local migration tool: it only understands the stable
``RGTHREE_CONTEXT`` transport shape and never imports another custom node.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ED_CONTEXT_TYPE = "Context Big 💬ED"
LEGACY_CONTEXT_TYPE = "Context Big (rgthree)"
ED_EXTRA_FIELDS = (
    ("lora_stack", "LORA_STACK", "LORA_STACK"),
    ("clip_encoder", "CLIP_ENCODER", "CLIP_ENCODER"),
    ("lora_pipe", "ED_LORA_PIPE", "LORA_PIPE"),
    ("xy_raw_positive", "STRING", "XY_RAW_POSITIVE"),
    ("xy_raw_negative", "STRING", "XY_RAW_NEGATIVE"),
    ("cnet_stack", "CONTROL_NET_STACK", "CNET_STACK"),
)


def _node_map(workflow):
    return {node["id"]: node for node in workflow["nodes"]}


def _socket_index(node, direction, name):
    for index, socket in enumerate(node.get(direction, [])):
        if socket.get("name") == name:
            return index
    raise ValueError(f"Node {node['id']} has no {direction} socket named {name}")


def _remove_link(workflow, link_id):
    nodes = _node_map(workflow)
    for index, link in enumerate(workflow["links"]):
        if link[0] != link_id:
            continue
        origin = nodes[link[1]]
        target = nodes[link[3]]
        origin_output = origin["outputs"][link[2]]
        if link_id in (origin_output.get("links") or []):
            origin_output["links"].remove(link_id)
        target["inputs"][link[4]]["link"] = None
        workflow["links"].pop(index)
        return
    raise ValueError(f"Link {link_id} was not found")


def _append_context_extensions(node):
    input_names = {entry.get("name") for entry in node.get("inputs", [])}
    output_names = {entry.get("name") for entry in node.get("outputs", [])}
    for input_name, input_type, output_name in ED_EXTRA_FIELDS:
        if input_name not in input_names:
            node["inputs"].append(
                {"dir": 3, "label": input_name, "name": input_name, "type": input_type, "link": None}
            )
        if output_name not in output_names:
            node["outputs"].append(
                {
                    "dir": 4,
                    "label": output_name,
                    "name": output_name,
                    "shape": 3,
                    "type": input_type,
                    "slot_index": len(node["outputs"]),
                    "links": [],
                }
            )


def _set_scheduler_metadata(node, schedulers):
    for direction in ("inputs", "outputs"):
        for socket in node.get(direction, []):
            if socket.get("name") == "scheduler" or socket.get("name") == "SCHEDULER":
                socket["type"] = list(schedulers)


def _migrate_loader_steps(loader, steps):
    values = loader.get("widgets_values")
    if isinstance(values, list) and len(values) > 8 and isinstance(values[8], str):
        values.insert(8, steps)
    input_names = {entry.get("name") for entry in loader.get("inputs", [])}
    if "steps" not in input_names:
        cfg_index = _socket_index(loader, "inputs", "cfg")
        loader["inputs"].insert(
            cfg_index + 1,
            {
                "label": "steps",
                "localized_name": "steps",
                "name": "steps",
                "type": "INT",
                "widget": {"name": "steps"},
                "link": None,
            },
        )


def _route_main_context_through_ed_big(workflow, context_id):
    nodes = _node_map(workflow)
    context = nodes[context_id]
    base_input_index = _socket_index(context, "inputs", "base_ctx")
    base_link_id = context["inputs"][base_input_index].get("link")
    if base_link_id is None:
        raise ValueError(f"Context Big {context_id} has no base context link")
    base_link = next(link for link in workflow["links"] if link[0] == base_link_id)
    loader_id = base_link[1]

    for link in workflow["links"]:
        if link[1] != loader_id or link[2] != 0 or link[3] == context_id:
            continue
        target = nodes[link[3]]
        if target.get("type") != "Wildcard Encode 💬ED":
            continue
        loader_output = nodes[loader_id]["outputs"][0]
        loader_output["links"].remove(link[0])
        context_output = context["outputs"][0]
        context_output.setdefault("links", []).append(link[0])
        link[1] = context_id
        link[2] = 0
        break
    else:
        raise ValueError("Could not find Loader -> Wildcard Encode ED context link")

    steps_input_index = _socket_index(context, "inputs", "steps")
    steps_link_id = context["inputs"][steps_input_index].get("link")
    if steps_link_id is not None:
        _remove_link(workflow, steps_link_id)


def validate_workflow(workflow):
    nodes = _node_map(workflow)
    link_ids = set()
    for link in workflow["links"]:
        link_id, source_id, source_slot, target_id, target_slot, _ = link
        if link_id in link_ids:
            raise ValueError(f"Duplicate link id {link_id}")
        link_ids.add(link_id)
        if source_id not in nodes or target_id not in nodes:
            raise ValueError(f"Link {link_id} references missing node")
        source = nodes[source_id]
        target = nodes[target_id]
        if source_slot >= len(source.get("outputs", [])):
            raise ValueError(f"Link {link_id} has invalid source socket")
        if target_slot >= len(target.get("inputs", [])):
            raise ValueError(f"Link {link_id} has invalid target socket")
        if link_id not in (source["outputs"][source_slot].get("links") or []):
            raise ValueError(f"Source socket omitted link {link_id}")
        if target["inputs"][target_slot].get("link") != link_id:
            raise ValueError(f"Target socket omitted link {link_id}")


def migrate_workflow(workflow, context_id, loader_steps, schedulers):
    context_ids = []
    for node in workflow["nodes"]:
        if node.get("type") in {LEGACY_CONTEXT_TYPE, ED_CONTEXT_TYPE}:
            node["type"] = ED_CONTEXT_TYPE
            _append_context_extensions(node)
            _set_scheduler_metadata(node, schedulers)
            context_ids.append(node["id"])

    if context_id not in context_ids:
        raise ValueError(f"Context Big node {context_id} was not found")

    loader_id = next(
        link[1] for link in workflow["links"]
        if link[3] == context_id and link[4] == 0
    )
    _migrate_loader_steps(_node_map(workflow)[loader_id], loader_steps)
    _route_main_context_through_ed_big(workflow, context_id)

    for link in workflow["links"]:
        source = _node_map(workflow)[link[1]]
        target = _node_map(workflow)[link[3]]
        if source.get("type") == ED_CONTEXT_TYPE and source["outputs"][link[2]].get("name") == "SCHEDULER":
            link[5] = list(schedulers)
        if target.get("type") == ED_CONTEXT_TYPE and target["inputs"][link[4]].get("name") == "scheduler":
            link[5] = list(schedulers)

    validate_workflow(workflow)
    return context_ids, loader_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--context-node-id", type=int, required=True)
    parser.add_argument("--loader-steps", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    comfy_root = Path(__file__).resolve().parents[3]
    if str(comfy_root) not in sys.path:
        sys.path.insert(0, str(comfy_root))
    from comfy.samplers import KSampler

    workflow = json.loads(args.source.read_text(encoding="utf-8"))
    context_ids, loader_id = migrate_workflow(
        workflow, args.context_node_id, args.loader_steps, list(KSampler.SCHEDULERS)
    )
    print(f"[ED-MIGRATE] context_nodes={context_ids} loader={loader_id} steps={args.loader_steps}")
    if not args.dry_run:
        args.destination.write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[ED-MIGRATE] wrote {args.destination}")


if __name__ == "__main__":
    main()
