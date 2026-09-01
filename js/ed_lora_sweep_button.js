import { app } from "../../../scripts/app.js";

const isSweep = (data) => String(data?.name || "").includes("LoRA Sweep");
const find = (node, name) => (node.widgets || []).find(w => w.name === name);
const isSweepNode = (node) => [node?.type, node?.comfyClass, node?.title,
    node?.properties?.["Node name for S&R"]].some(v => String(v || "").includes("LoRA Sweep"));

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
    if (!target || !names) {
        console.debug("[ED LoRA Sweep] waiting for connected Power Loader stack", {
            node: node.id, hasTarget: !!target, names: names?.length || 0,
        });
        return;
    }
    target.options ||= {};
    target.options.values = ["None", ...names];
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

function menuEvent(node, callbackArgs = []) {
    // LiteGraph button callbacks differ between frontend versions. Only accept
    // an actual pointer event; canvas/node arguments previously caused (0, 0)
    // menus and swallowed the selection callback.
    const pointer = callbackArgs.find((value) => value &&
        Number.isFinite(value.clientX) && Number.isFinite(value.clientY));
    if (pointer) return pointer;
    const last = app.canvas?.last_mouse_event || app.canvas?.lastMouseEvent;
    if (last && Number.isFinite(last.clientX) && Number.isFinite(last.clientY)) return last;
    const rect = app.canvas?.canvas?.getBoundingClientRect?.();
    return rect ? { clientX: rect.left + 24, clientY: rect.top + 24 } : { clientX: 24, clientY: 24 };
}

function addRowWithChooser(node, callbackArgs) {
    const names = stackNames(node) || ["None"];
    new LiteGraph.ContextMenu(names, {
        event: menuEvent(node, callbackArgs),
        title: "Choose a LoRA from Power Loader",
        className: "dark",
        callback: (value) => {
        const selected = typeof value === "string" ? value : value?.content;
        if (selected && selected !== "None") {
            addRow(node, selected);
            node.setDirtyCanvas(true, true);
        }
        },
    });
}

function hasSweepAddButton(node) {
    return (node.widgets || []).some(widget => widget.__edSweepAddButton === true);
}

function installSweepAddButton(node) {
    if (hasSweepAddButton(node)) return;
    const button = node.addWidget("button", "➕ Add Lora", null,
        (...args) => addRowWithChooser(node, args), { serialize: false });
    // Use an object marker instead of the display label. ComfyUI may normalize
    // button names, so checking `widget.name` was not stable.
    button.__edSweepAddButton = true;
}

app.registerExtension({
    name: "ED.StandaloneLoRASweepButton",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isSweep(nodeData)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            original?.apply(this, arguments);
            installSweepAddButton(this);
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
        ensureSweepNode(node);
    },
    afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) ensureSweepNode(node);
    },
});

function ensureSweepNode(node) {
    if (!isSweepNode(node)) return;
    installSweepAddButton(node);
    refreshTarget(node);
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
}

// Power Loader creates its rows dynamically, so a lightweight refresh keeps
// existing Sweep combo boxes synchronized without requiring reconnection.
setInterval(() => {
    for (const node of app.graph?._nodes || []) {
        if (String(node.type || node.comfyClass || node.title || "").includes("LoRA Sweep")) refreshTarget(node);
    }
}, 1000);
