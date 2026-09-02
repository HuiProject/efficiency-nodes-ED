import { app } from "../../scripts/app.js";

const NODE_NAME = "XY Input: LoRA";
const MAX_ROWS = 50;
const HIDDEN_TYPE = "ed_legacy_xy_hidden";

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function isNode(node) {
    return node?.comfyClass === NODE_NAME || node?.type === NODE_NAME;
}

function setVisible(item, visible) {
    if (!item) return;
    if (item.__edLegacyXYOriginalType === undefined) {
        item.__edLegacyXYOriginalType = item.type;
        item.__edLegacyXYOriginalComputeSize = item.computeSize;
    }
    item.type = visible ? item.__edLegacyXYOriginalType : HIDDEN_TYPE;
    item.computeSize = visible ? item.__edLegacyXYOriginalComputeSize : () => [0, -4];
}

function refresh(node) {
    const count = Math.max(0, Math.min(MAX_ROWS, Number(widget(node, "lora_count")?.value ?? 0)));
    const mode = String(widget(node, "input_mode")?.value ?? "LoRA Names");
    const batchMode = mode.includes("Batch");
    const weighted = mode.includes("Weights");
    for (let index = 1; index <= MAX_ROWS; index += 1) {
        const active = index <= count && !batchMode;
        setVisible(widget(node, `lora_name_${index}`), active);
        setVisible(widget(node, `model_str_${index}`), active && weighted);
        setVisible(widget(node, `clip_str_${index}`), active && weighted);
    }
    node.setSize([node.size[0], Math.max(120, node.computeSize()[1])]);
    node.setDirtyCanvas(true, true);
}

function install(node) {
    if (!isNode(node) || node.__edLegacyXYWidgetsInstalled) return;
    node.__edLegacyXYWidgetsInstalled = true;
    for (const name of ["lora_count", "input_mode"]) {
        const item = widget(node, name);
        if (!item) continue;
        const original = item.callback;
        item.callback = function (value) {
            const result = original?.apply(this, arguments);
            refresh(node);
            return result;
        };
    }
    refresh(node);
}

app.registerExtension({
    name: "ED.LegacyXYLoraWidgets",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME || nodeType.prototype.__edLegacyXYPatched) return;
        nodeType.prototype.__edLegacyXYPatched = true;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = original?.apply(this, arguments);
            install(this);
            return result;
        };
    },
    nodeCreated(node) { install(node); },
    async afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) install(node);
    },
});
