import { app } from "../../scripts/app.js";

const NODE_NAME = "LoRA Stacker";
const MAX_ROWS = 50;
const HIDE_TYPE = "ed_legacy_hidden";

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function setVisible(node, item, visible) {
    if (!item) return;
    if (item.__edLegacyOriginalType === undefined) {
        item.__edLegacyOriginalType = item.type;
        item.__edLegacyOriginalComputeSize = item.computeSize;
    }
    item.type = visible ? item.__edLegacyOriginalType : HIDE_TYPE;
    item.computeSize = visible ? item.__edLegacyOriginalComputeSize : () => [0, -4];
}

function refresh(node) {
    const count = Math.max(0, Math.min(MAX_ROWS, Number(widget(node, "lora_count")?.value ?? 0)));
    const mode = widget(node, "input_mode")?.value ?? "simple";
    for (let index = 1; index <= MAX_ROWS; index += 1) {
        const active = index <= count;
        setVisible(node, widget(node, `lora_name_${index}`), active);
        setVisible(node, widget(node, `lora_wt_${index}`), active && mode === "simple");
        setVisible(node, widget(node, `model_str_${index}`), active && mode === "advanced");
        setVisible(node, widget(node, `clip_str_${index}`), active && mode === "advanced");
    }
    node.setSize([node.size[0], Math.max(120, node.computeSize()[1])]);
    node.setDirtyCanvas(true, true);
}

function install(node) {
    if (!node || node.comfyClass !== NODE_NAME || node.__edLegacyCompatInstalled) return;
    node.__edLegacyCompatInstalled = true;
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
    name: "ED.LegacyCompatWidgets",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME || nodeType.prototype.__edLegacyCompatPatched) return;
        nodeType.prototype.__edLegacyCompatPatched = true;
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

