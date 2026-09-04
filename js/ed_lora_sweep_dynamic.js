import { app } from "../../scripts/app.js";

// Dynamic Stacker-style rows for XY Input: LoRA Sweep. The Python node only
// declares base inputs; every row below is a real LiteGraph widget created on
// demand and serialized with the node.
const MAX_ROWS = 50;
const ROW_RE = /^scan_lora_name_(\d+)$/;

function isSweep(data) {
    return [data?.name, data?.comfyClass, data?.type, data?.title,
        data?.properties?.["Node name for S&R"]]
        .some(value => String(value || "").includes("XY Input: LoRA Sweep"));
}

function widget(node, name) {
    return (node.widgets || []).find(item => item.name === name);
}

function rowWidgets(node, index) {
    return {
        name: widget(node, `scan_lora_name_${index}`),
        toggle: widget(node, `scan_lora_${index}_toggle`),
        first: widget(node, `scan_lora_first_strength_${index}`),
        last: widget(node, `scan_lora_last_strength_${index}`),
    };
}

function connectedStackNames(node) {
    const input = (node.inputs || []).find(item => item.name === "lora_pipe");
    const link = input?.link != null ? app.graph?.links?.[input.link] : null;
    const origin = link ? app.graph?.getNodeById(link.origin_id) : null;
    // During graph restore the node can be created before its link records are
    // attached. Keep saved row values intact until the connection is visible;
    // treating that transient state as an empty stack would erase selections.
    if (!origin) return null;

    const names = [];
    for (const item of origin.widgets || []) {
        const value = item.value;
        // Power Loader rows are serialized as {on, lora, strength, ...}.
        if (value && typeof value === "object" && typeof value.lora === "string" &&
            value.lora && !names.includes(value.lora)) {
            names.push(value.lora);
        }
    }
    return ["None", ...names];
}

function hideWidget(item) {
    if (!item || item.__edSweepHidden) return;
    item.__edSweepHidden = true;
    item.__edSweepOriginalType = item.type;
    item.__edSweepOriginalComputeSize = item.computeSize;
    item.type = "hidden";
    item.computeSize = () => [0, -4];
}

// Vanilla LiteGraph in ComfyUI 0.30.2 has no stable removeWidget method on
// every node class.  The old index-only call could throw while lowering
// lora_count, removing the remaining rows from the canvas.  Prefer the node
// API when available and fall back to a direct, deterministic splice.
function removeWidgetSafe(node, item) {
    if (!item || !Array.isArray(node.widgets)) return;
    const index = node.widgets.indexOf(item);
    if (index < 0) return;
    if (typeof node.removeWidget === "function") {
        try {
            node.removeWidget(item);
            if (!node.widgets.includes(item)) return;
        } catch (error) {
            console.debug("[ED-UI] Sweep removeWidget fallback", error);
        }
    }
    node.widgets.splice(index, 1);
    item.onRemove?.();
}

function countValue(value, fallback) {
    const candidate = value && typeof value === "object" ? value.value : value;
    const parsed = Number(candidate);
    return Number.isFinite(parsed) ? parsed : Number(fallback) || 0;
}

function showWidget(item) {
    if (!item?.__edSweepHidden) return;
    item.type = item.__edSweepOriginalType;
    item.computeSize = item.__edSweepOriginalComputeSize;
    item.__edSweepHidden = false;
}

function refreshChoices(node) {
    const choices = connectedStackNames(node);
    if (!choices) return;
    for (let index = 1; index <= MAX_ROWS; index++) {
        const item = widget(node, `scan_lora_name_${index}`);
        if (!item) continue;
        item.options = item.options || {};
        item.options.values = choices;
        if (!choices.includes(item.value)) item.value = "None";
    }
    console.debug("[ED-UI] Sweep stack choices", { node: node.id, count: choices.length - 1 });
}

function addRow(node, index, values = {}) {
    const choices = connectedStackNames(node) || ["None"];
    const name = node.addWidget("combo", `scan_lora_name_${index}`,
        values.name ?? "None", () => {}, { values: choices, serialize: true });
    name.label = `L${index}`;
    const toggle = node.addWidget("toggle", `scan_lora_${index}_toggle`,
        values.toggle ?? true, () => {}, { serialize: true });
    const first = node.addWidget("number", `scan_lora_first_strength_${index}`,
        Number(values.first ?? 0.5), () => {}, { min: -10, max: 10, step: 0.01, serialize: true });
    const last = node.addWidget("number", `scan_lora_last_strength_${index}`,
        Number(values.last ?? 1.0), () => {}, { min: -10, max: 10, step: 0.01, serialize: true });
    first.label = `L${index} Strength 起`;
    last.label = `L${index} Strength 止`;
    for (const item of [name, toggle, first, last]) {
        if (item) item.serialize = true;
    }
    console.debug("[ED-UI] Sweep row created", { node: node.id, index, lora: name?.value });
}

function removeRow(node, index) {
    const parts = rowWidgets(node, index);
    // Remove in reverse order so widget indexes remain stable.
    for (const item of [parts.last, parts.first, parts.toggle, parts.name]) {
        if (!item) continue;
        removeWidgetSafe(node, item);
    }
}

function ensureRows(node, requested) {
    const count = Math.max(0, Math.min(MAX_ROWS, Number(requested) || 0));
    let existing = [];
    for (const item of node.widgets || []) {
        const match = ROW_RE.exec(item.name || "");
        if (match) existing.push(Number(match[1]));
    }
    const current = existing.length ? Math.max(...existing) : 0;
    for (let index = current + 1; index <= count; index++) addRow(node, index);
    for (let index = current; index > count; index--) removeRow(node, index);
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
    return count;
}

function restoreSavedRows(node) {
    if (node.__edSweepRowsRestored) return;
    const saved = node.__edSweepSavedValues;
    let countWidget = widget(node, "lora_count");
    let count = Number(countWidget?.value);
    let legacyName = null;
    let legacyFirst = 0.5;
    let legacyLast = 1.0;
    // Both versions retain legacy fields. New compact nodes have a numeric
    // lora_count at index 5; older nodes have no such value and start with a
    // single target at index 2.
    const hasCompactCount = Array.isArray(saved) && saved[5] !== null &&
        saved[5] !== undefined && Number.isFinite(Number(saved[5]));
    if (!hasCompactCount && Array.isArray(saved) && typeof saved[2] === "string") {
        legacyName = saved[2];
        legacyFirst = Number(saved[3] ?? legacyFirst);
        legacyLast = Number(saved[4] ?? legacyLast);
        count = legacyName && legacyName !== "None" ? 1 : 0;
    } else if (hasCompactCount) {
        count = Number(saved[5]);
    }
    if (!Number.isFinite(count)) count = legacyName ? 1 : 0;
    // Workflows saved before lora_count existed have no count widget. Add a
    // real LiteGraph widget during migration so the compact UI is usable and
    // the value is serialized on the next save.
    if (!countWidget && typeof node.addWidget === "function") {
        countWidget = node.addWidget("number", "lora_count", count, () => {},
            { min: 0, max: MAX_ROWS, step: 1, serialize: true });
        countWidget.serialize = true;
        console.debug("[ED-UI] migrated missing lora_count", { node: node.id, count });
    }
    if (countWidget) countWidget.value = count;
    ensureRows(node, count);

    // Current format: base widgets occupy indexes 0..5, followed by rows.
    if (!legacyName && hasCompactCount && Array.isArray(saved) && saved.length > 6) {
        let offset = 6;
        for (let index = 1; index <= count; index++) {
            const parts = rowWidgets(node, index);
            if (!parts.name) continue;
            if (saved[offset] !== undefined) parts.name.value = saved[offset];
            if (saved[offset + 1] !== undefined) parts.toggle.value = saved[offset + 1];
            if (saved[offset + 2] !== undefined) parts.first.value = saved[offset + 2];
            if (saved[offset + 3] !== undefined) parts.last.value = saved[offset + 3];
            offset += 4;
        }
    } else if (count === 1 && legacyName && legacyName !== "None") {
        const parts = rowWidgets(node, 1);
        parts.name.value = legacyName;
        parts.first.value = legacyFirst;
        parts.last.value = legacyLast;
    }
    refreshChoices(node);
    node.__edSweepRowsRestored = true;
}

function initialize(node) {
    if (!isSweep(node) || node.__edSweepDynamicInitialized) return;
    node.__edSweepDynamicInitialized = true;
    node.serialize_widgets = true;
    hideWidget(widget(node, "target_lora"));
    hideWidget(widget(node, "first_strength"));
    hideWidget(widget(node, "last_strength"));

    let countWidget = widget(node, "lora_count");
    if (!countWidget && !node.__edSweepRowsRestored && node.widgets?.length) {
        // A legacy node may be instantiated from an old definition before the
        // current INPUT_TYPES metadata is applied. The migration pass below
        // creates the missing count widget after onConfigure captured values.
        console.debug("[ED-UI] lora_count pending migration", { node: node.id });
    }
    if (countWidget) {
        const originalCallback = countWidget.callback;
        countWidget.callback = function (value) {
            originalCallback?.apply(this, arguments);
            const current = countValue(value, countWidget.value);
            ensureRows(node, current);
            refreshChoices(node);
            console.debug("[ED-UI] Sweep count changed", { node: node.id, count: current });
        };
    }

    // ComfyUI 0.30.x notifies Vue/LiteGraph widget edits through the node-level
    // hook. The legacy widget callback is still wrapped above for older builds,
    // but relying on it alone leaves stale rows after clicking +/- in 1.47.x.
    const originalOnWidgetChanged = node.onWidgetChanged;
    node.onWidgetChanged = function (name, value, changedWidget) {
        const result = originalOnWidgetChanged?.apply(this, arguments);
        const widgetName = typeof name === "string" ? name : name?.name ?? changedWidget?.name;
        if (this.__edSweepSyncing) return result;
        if (widgetName === "lora_count") {
            this.__edSweepSyncing = true;
            try {
                const current = (typeof name === "object" ? name.value : value) ??
                    changedWidget?.value ?? widget(this, "lora_count")?.value;
                ensureRows(this, current);
                refreshChoices(this);
                console.debug("[ED-UI] Sweep count changed", { node: this.id, count: Number(current) });
            } finally {
                this.__edSweepSyncing = false;
            }
        } else if (typeof widgetName === "string" && widgetName.startsWith("scan_lora_name_")) {
            refreshChoices(this);
            this.setDirtyCanvas(true, true);
        }
        return result;
    };

    // Some 1.47.x editor paths update the widget value without dispatching the
    // legacy callback or node hook. Reconcile once per draw so stale rows from
    // an older tab/workflow cannot remain visible or reach graphToPrompt.
    const originalDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
        if (!this.__edSweepSyncing) {
            const count = Number(widget(this, "lora_count")?.value ?? 0);
            const indexes = (this.widgets || []).map(item => {
                const match = ROW_RE.exec(item.name || "");
                return match ? Number(match[1]) : 0;
            });
            const actual = indexes.length ? Math.max(...indexes) : 0;
            if (actual !== Math.max(0, Math.min(MAX_ROWS, count))) {
                this.__edSweepSyncing = true;
                try { ensureRows(this, count); } finally { this.__edSweepSyncing = false; }
            }
        }
        return originalDrawForeground?.apply(this, arguments);
    };
    ensureRows(node, countWidget?.value ?? 1);

    const originalConnections = node.onConnectionsChange;
    node.onConnectionsChange = function () {
        const result = originalConnections?.apply(this, arguments);
        refreshChoices(this);
        return result;
    };
    refreshChoices(node);
}

app.registerExtension({
    name: "ED.LoRASweepDynamicStacker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isSweep(nodeData) || nodeType.prototype.__edSweepPatched) return;
        nodeType.prototype.__edSweepPatched = true;
        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            this.__edSweepSavedValues = info?.widgets_values;
            return originalConfigure?.apply(this, arguments);
        };
    },
    nodeCreated(node) { initialize(node); },
    async afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) {
            initialize(node);
            if (isSweep(node)) restoreSavedRows(node);
        }
    },
});

// Power Loader rows are editable after the graph is connected. Refresh only
// existing combo options; no widgets or page-level menus are created here.
setInterval(() => {
    for (const node of app.graph?._nodes || []) {
        if (!isSweep(node)) continue;
        refreshChoices(node);
    }
}, 1000);
