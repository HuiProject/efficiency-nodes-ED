import { app } from "../../scripts/app.js";

// Compact, node-owned rows for XY Input: LoRA Plot.  The selector is a real
// LiteGraph widget; no page-level menu or floating DOM state is used.
const NODE_NAME = "XY Input: LoRA Plot";
const MAX_ROWS = 50;
const ROW_RE = /^scan_lora_name_(\d+)$/;

function isPlot(data) {
    return [data?.name, data?.comfyClass, data?.type, data?.title,
        data?.properties?.["Node name for S&R"]]
        .some(value => String(value || "") === NODE_NAME);
}

function widget(node, name) {
    return (node.widgets || []).find(item => item.name === name);
}

function rowWidgets(node, index) {
    return {
        name: widget(node, `scan_lora_name_${index}`),
        toggle: widget(node, `scan_lora_${index}_toggle`),
    };
}

function connectedStackNames(node) {
    const input = (node.inputs || []).find(item => item.name === "lora_pipe" || item.name === "lora_stack");
    const link = input?.link != null ? app.graph?.links?.[input.link] : null;
    const origin = link ? app.graph?.getNodeById(link.origin_id) : null;
    if (!origin) return null;
    const names = [];
    for (const item of origin.widgets || []) {
        const value = item.value;
        if (value && typeof value === "object") {
            const name = value.lora ?? value.name;
            if (typeof name === "string" && name && !names.includes(name)) names.push(name);
        }
    }
    return ["None", ...names];
}

function hideWidget(item) {
    if (!item || item.__edPlotHidden) return;
    item.__edPlotHidden = true;
    item.__edPlotOriginalType = item.type;
    item.__edPlotOriginalComputeSize = item.computeSize;
    item.type = "hidden";
    item.computeSize = () => [0, -4];
}

function refreshChoices(node) {
    const choices = connectedStackNames(node);
    if (!choices) return;
    for (let index = 1; index <= MAX_ROWS; index += 1) {
        const item = widget(node, `scan_lora_name_${index}`);
        if (!item) continue;
        item.options = item.options || {};
        item.options.values = choices;
        if (!choices.includes(item.value)) item.value = "None";
    }
    console.debug("[ED-UI] LoRA Plot stack choices", { node: node.id, count: choices.length - 1 });
}

function addRow(node, index, values = {}) {
    const choices = connectedStackNames(node) || ["None"];
    node.addWidget("combo", `scan_lora_name_${index}`, values.name ?? "None",
        () => {}, { values: choices, serialize: true });
    node.addWidget("toggle", `scan_lora_${index}_toggle`, values.toggle ?? true,
        () => {}, { serialize: true });
    console.debug("[ED-UI] LoRA Plot row created", { node: node.id, index, lora: values.name ?? "None" });
}

function removeRow(node, index) {
    const parts = rowWidgets(node, index);
    for (const item of [parts.toggle, parts.name]) {
        const at = node.widgets?.indexOf(item);
        if (at >= 0) node.removeWidget(at);
    }
}

function ensureRows(node, requested) {
    const count = Math.max(0, Math.min(MAX_ROWS, Number(requested) || 0));
    const indexes = (node.widgets || []).map(item => {
        const match = ROW_RE.exec(item.name || "");
        return match ? Number(match[1]) : 0;
    }).filter(Boolean);
    const current = indexes.length ? Math.max(...indexes) : 0;
    for (let index = current + 1; index <= count; index += 1) addRow(node, index);
    for (let index = current; index > count; index -= 1) removeRow(node, index);
    node.setSize([node.size[0], Math.max(140, node.computeSize()[1])]);
    node.setDirtyCanvas(true, true);
    return count;
}

function restoreSaved(node) {
    if (node.__edPlotRowsRestored) return;
    const saved = node.__edPlotSavedValues;
    const countWidget = widget(node, "lora_count");
    let count = Number(countWidget?.value ?? 1);
    let rows = [];
    if (Array.isArray(saved)) {
        // Canonical compact layout: seven base widgets followed by name/toggle pairs.
        if (saved.length >= 7 && Number.isFinite(Number(saved[0]))) {
            count = Number(saved[0]);
            for (let i = 0; i < count; i += 1) {
                rows.push({ name: saved[7 + i * 2], toggle: saved[8 + i * 2] });
            }
        // Historical layout migration: input_mode, lora_name, model_strength,
        // clip_strength, X_batch_count, path, subdirs, sort, X first/last,
        // Y batch/first/last.
        } else if (saved.length >= 13 && typeof saved[0] === "string") {
            count = saved[1] && saved[1] !== "None" ? 1 : 0;
            rows = count ? [{ name: saved[1], toggle: true }] : [];
            const values = {
                X_batch_count: saved[4], X_first_value: saved[8], X_last_value: saved[9],
                Y_batch_count: saved[10], Y_first_value: saved[11], Y_last_value: saved[12],
            };
            for (const [name, value] of Object.entries(values)) {
                const item = widget(node, name);
                if (item && value !== undefined) item.value = value;
            }
            console.debug("[ED-UI] migrated historical LoRA Plot widgets", { node: node.id });
        }
    }
    if (countWidget) countWidget.value = count;
    ensureRows(node, count);
    rows.forEach((value, offset) => {
        const parts = rowWidgets(node, offset + 1);
        if (parts.name && value.name !== undefined) parts.name.value = value.name;
        if (parts.toggle && value.toggle !== undefined) parts.toggle.value = value.toggle;
    });
    refreshChoices(node);
    node.__edPlotRowsRestored = true;
}

function initialize(node) {
    if (!isPlot(node) || node.__edPlotDynamicInitialized) return;
    node.__edPlotDynamicInitialized = true;
    node.serialize_widgets = true;
    const count = widget(node, "lora_count");
    if (count) {
        const original = count.callback;
        count.callback = function(value) {
            const result = original?.apply(this, arguments);
            ensureRows(node, value);
            refreshChoices(node);
            console.debug("[ED-UI] LoRA Plot count changed", { node: node.id, count: Number(value) });
            return result;
        };
    }
    const originalOnWidgetChanged = node.onWidgetChanged;
    node.onWidgetChanged = function(name, value, changedWidget) {
        const result = originalOnWidgetChanged?.apply(this, arguments);
        const widgetName = typeof name === "string" ? name : name?.name ?? changedWidget?.name;
        if (widgetName === "lora_count" && !this.__edPlotSyncing) {
            this.__edPlotSyncing = true;
            try { ensureRows(this, value ?? widget(this, "lora_count")?.value); }
            finally { this.__edPlotSyncing = false; }
        }
        if (typeof widgetName === "string" && widgetName.startsWith("scan_lora_name_")) refreshChoices(this);
        return result;
    };
    const originalConnections = node.onConnectionsChange;
    node.onConnectionsChange = function() {
        const result = originalConnections?.apply(this, arguments);
        refreshChoices(this);
        return result;
    };
    ensureRows(node, count?.value ?? 1);
    refreshChoices(node);
}

app.registerExtension({
    name: "ED.LoRAPlotDynamicStack",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isPlot(nodeData) || nodeType.prototype.__edPlotPatched) return;
        nodeType.prototype.__edPlotPatched = true;
        const original = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(info) {
            this.__edPlotSavedValues = info?.widgets_values;
            return original?.apply(this, arguments);
        };
    },
    nodeCreated(node) { initialize(node); },
    async afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) {
            initialize(node);
            if (isPlot(node)) restoreSaved(node);
        }
    },
});

