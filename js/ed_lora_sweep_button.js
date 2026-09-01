import { app } from "../../../scripts/app.js";
import { showLoraChooser } from "../../rgthree-comfy/web/comfyui/utils_menu.js";

const isSweep = (data) => String(data?.name || "").includes("LoRA Sweep");
const find = (node, name) => (node.widgets || []).find(w => w.name === name);

function stackNames(node) {
    const input = (node.inputs || []).find(i => i.name === "lora_pipe");
    const link = input?.link != null ? app.graph.links[input.link] : null;
    const origin = link ? app.graph.getNodeById(link.origin_id) : null;
    if (!origin) return null;
    const result = [];
    for (const w of origin.widgets || []) {
        const v = w.value;
        if (v && typeof v === "object" && v.lora && !result.includes(v.lora)) result.push(v.lora);
    }
    return result.length ? result : null;
}

function refreshTarget(node) {
    const names = stackNames(node);
    const target = find(node, "target_lora");
    if (!target || !names) return;
    target.options ||= {};
    target.options.values = names;
    if (!names.includes(target.value)) target.value = names[0];
    node.setDirtyCanvas(true, true);
}

function addRow(node, selectedName = "None") {
    const index = 1 + (node.widgets || []).filter(w => /^scan_lora_name_\d+$/.test(w.name || "")).length;
    if (index > 9) return;
    const names = stackNames(node) || ["None"];
    node.addWidget("combo", `scan_lora_name_${index}`, names, names.includes(selectedName) ? selectedName : names[0]);
    node.addWidget("toggle", `scan_lora_${index}_toggle`, true);
    node.addWidget("number", `scan_lora_first_strength_${index}`, 0.5, null, {min:-10,max:10,step:0.01});
    node.addWidget("number", `scan_lora_last_strength_${index}`, 1.0, null, {min:-10,max:10,step:0.01});
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
};

function addRowWithChooser(node, event) {
    const names = stackNames(node) || ["None"];
    showLoraChooser(event || window.event || {clientX: 0, clientY: 0}, (value) => {
        if (value && value !== "None") addRow(node, value);
    }, undefined, names);
}

app.registerExtension({
    name: "ED.StandaloneLoRASweepButton",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isSweep(nodeData)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            original?.apply(this, arguments);
            if (!this.widgets?.some(w => w.name === "ed_add_lora_sweep")) {
                this.addWidget("button", "➕ Add Lora", null, (value, event) => addRowWithChooser(this, event), {
                    serialize: false, property: "ed_add_lora_sweep"
                });
            }
            refreshTarget(this);
            const old = this.onConnectionsChange;
            if (!this.__edSweepStandaloneBound) {
                this.__edSweepStandaloneBound = true;
                this.onConnectionsChange = function () {
                    const result = old?.apply(this, arguments);
                    refreshTarget(this);
                    return result;
                };
            }
            this.setDirtyCanvas(true, true);
        };
    },
    nodeCreated(node) {
        if (String(node.type || node.comfyClass || node.title || "").includes("LoRA Sweep")) {
            refreshTarget(node);
        }
    },
});

// Power Loader creates its rows dynamically, so a lightweight refresh keeps
// existing Sweep combo boxes synchronized without requiring reconnection.
setInterval(() => {
    for (const node of app.graph?._nodes || []) {
        if (String(node.type || node.comfyClass || node.title || "").includes("LoRA Sweep")) refreshTarget(node);
    }
}, 1000);
