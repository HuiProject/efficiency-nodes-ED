import { app } from "../../../scripts/app.js";

const isSweep = (data) => [data?.name, data?.comfyClass, data?.type, data?.title,
    data?.properties?.["Node name for S&R"]].some(v => String(v || "").includes("LoRA Sweep"));
const isSweepNode = (node) => isSweep(node);
const findWidget = (node, name) => (node.widgets || []).find(w => w.name === name);

function stackNames(node) {
    const input = (node.inputs || []).find(i => i.name === "lora_pipe");
    const link = input?.link != null ? app.graph.links[input.link] : null;
    const origin = link ? app.graph.getNodeById(link.origin_id) : null;
    if (!origin) return ["None"];
    const names = [];
    for (const w of origin.widgets || []) {
        const v = w.value;
        if (v && typeof v === "object" && typeof v.lora === "string" && !names.includes(v.lora)) names.push(v.lora);
    }
    return ["None", ...names];
}

function resize(node) {
    const size = node.computeSize();
    node.size[0] = Math.max(node.size[0] || 0, size[0]);
    node.size[1] = size[1];
    node.setDirtyCanvas(true, true);
}

function addRow(node, selected) {
    if (!selected || selected === "None") return;
    const index = 1 + (node.widgets || []).filter(w => /^scan_lora_name_\d+$/.test(w.name || "")).length;
    if (index > 9) {
        console.warn("[ED-UI] LoRA Sweep maximum of 9 rows reached", node.id);
        return;
    }
    const values = stackNames(node);
    node.addWidget("combo", `scan_lora_name_${index}`, values, selected);
    node.addWidget("toggle", `scan_lora_${index}_toggle`, true);
    node.addWidget("number", `scan_lora_first_strength_${index}`, 0.5, null, { min: -10, max: 10, step: 0.01 });
    node.addWidget("number", `scan_lora_last_strength_${index}`, 1.0, null, { min: -10, max: 10, step: 0.01 });
    resize(node);
    console.debug("[ED-UI] LoRA Sweep row added", { node: node.id, index, lora: selected });
}

function addNextFromStack(node) {
    const values = stackNames(node);
    if (values.length <= 1) {
        console.warn("[ED-UI] LoRA Sweep chooser has no connected Power Loader entries", node.id);
        return;
    }
    const existing = new Set((node.widgets || [])
        .filter(w => /^scan_lora_name_\d+$/.test(w.name || ""))
        .map(w => w.value));
    const selected = values.slice(1).find(name => !existing.has(name));
    if (!selected) {
        console.warn("[ED-UI] all connected LoRAs are already added", node.id);
        return;
    }
    console.debug("[ED-UI] direct Add Lora probe", { node: node.id, selected });
    addRow(node, selected);
}

function install(node) {
    if (!isSweepNode(node)) return;
    if ((node.widgets || []).some(w => w.__edSweepAddButton)) return;
    const button = node.addWidget("button", "➕ Add Lora", null, () => addNextFromStack(node));
    button.__edSweepAddButton = true;
    button.serialize = false;
    button.options = button.options || {};
    button.options.serialize = false;
    resize(node);
    console.debug("[ED-UI] LoRA Sweep button installed", { node: node.id, choices: stackNames(node).length - 1 });
}

function refresh(node) {
    if (!isSweepNode(node)) return;
    const button = (node.widgets || []).find(w => w.__edSweepAddButton);
    if (button) button.__edSweepChoices = stackNames(node);
}

app.registerExtension({
    name: "ED.LoRASweepButtonV302",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isSweep(nodeData)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            original?.apply(this, arguments);
            install(this);
        };
    },
    nodeCreated(node) { install(node); refresh(node); },
    async afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) { install(node); refresh(node); }
    },
});

setInterval(() => {
    for (const node of app.graph?._nodes || []) if (isSweepNode(node)) refresh(node);
}, 1000);
