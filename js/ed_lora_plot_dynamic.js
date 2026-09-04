import { app } from "../../scripts/app.js";

// ED-owned dynamic editor for the legacy post-stack LoRA Plot node.
// The selector and toggle are one node-owned visual row; the hidden toggle and
// six-value row contract are still serialized independently for Python.
const NODE_NAME = "XY Input: LoRA Plot";
const MAX_ROWS = 50;
const ROW_RE = /^scan_lora_name_(\d+)$/;
const GLOBAL_RANGES = ["X_first_value", "X_last_value", "Y_first_value", "Y_last_value"];

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
        selector: widget(node, `scan_lora_name_${index}`),
        toggle: widget(node, `scan_lora_${index}_toggle`),
        xFirst: widget(node, `scan_lora_x_first_strength_${index}`),
        xLast: widget(node, `scan_lora_x_last_strength_${index}`),
        yFirst: widget(node, `scan_lora_y_first_strength_${index}`),
        yLast: widget(node, `scan_lora_y_last_strength_${index}`),
    };
}

function connectedStackNames(node) {
    const input = (node.inputs || []).find(item => item.name === "lora_pipe" || item.name === "lora_stack");
    const link = input?.link != null ? app.graph?.links?.[input.link] : null;
    const origin = link ? app.graph?.getNodeById(link.origin_id) : null;
    // A graph can restore widgets before links. Never clear saved choices in
    // that transient state; refresh again once the connection exists.
    if (!origin) return null;
    const names = [];
    for (const item of origin.widgets || []) {
        const value = item.value;
        const name = value && typeof value === "object" ? (value.lora ?? value.name) : null;
        if (typeof name === "string" && name && !names.includes(name)) names.push(name);
    }
    return ["None", ...names];
}

function hideWidget(item) {
    if (!item) return;
    if (!item.__edPlotHidden) {
        item.__edPlotOriginalType = item.type;
        item.__edPlotOriginalComputeSize = item.computeSize;
    }
    item.__edPlotHidden = true;
    // `tschide` is ComfyUI's supported hidden-widget type (the ED utility
    // uses the same prefix).  A plain `hidden` type is still drawn by the
    // 1.47 frontend, which is why old fields reappeared outside the node.
    item.type = "tschide";
    item.computeSize = () => [0, -4];
    item.hidden = true;
    item.options = item.options || {};
    item.options.hidden = true;
}

// ComfyUI 0.30.2 uses the vanilla LiteGraph node for ED nodes; unlike
// rgthree's BaseNode it does not always expose removeWidget().  Calling the
// optional method unconditionally made lowering lora_count throw and left a
// visually empty/broken node.  Keep removal local and accept either API.
function removeWidgetSafe(node, item) {
    if (!item || !Array.isArray(node.widgets)) return;
    const index = node.widgets.indexOf(item);
    if (index < 0) return;
    if (typeof node.removeWidget === "function") {
        try {
            node.removeWidget(item);
            if (!node.widgets.includes(item)) return;
        } catch (error) {
            console.debug("[ED-UI] Plot removeWidget fallback", error);
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

function openChoices(event, choices, callback) {
    new LiteGraph.ContextMenu(choices || ["None"], {
        event,
        scale: Math.max(1, app.canvas?.ds?.scale ?? 1),
        className: "dark",
        callback: value => {
            if (typeof value === "string") callback(value);
        },
    });
}

function fitText(ctx, value, width) {
    let text = String(value || "None");
    if (ctx.measureText(text).width <= width) return text;
    while (text.length > 1 && ctx.measureText(`${text}…`).width > width) text = text.slice(0, -1);
    return `${text}…`;
}

class PlotLoraRowWidget {
    constructor(combo, toggle, node, index) {
        this.name = combo.name;
        this.label = `LoRA ${index}`;
        this.value = combo.value ?? "None";
        this.options = combo.options || { values: ["None"] };
        this.node = node;
        this.toggleWidget = toggle;
        this.index = index;
        this.type = "ed_plot_lora_row";
        this.serialize = true;
        this.y = 0;
        this.last_y = 0;
    }

    get enabled() { return this.toggleWidget?.value !== false; }

    computeSize(width) {
        return [width || 220, LiteGraph.NODE_WIDGET_HEIGHT];
    }

    serializeValue() { return this.value; }

    draw(ctx, node, width, y, height) {
        const h = height || LiteGraph.NODE_WIDGET_HEIGHT;
        const left = 15;
        // LiteGraph may pass a stale width after a node is moved/resized. Use
        // the live node width as the upper bound so this model bar always has
        // the same inner margins as the numeric bars and never protrudes from
        // the node frame.
        const liveWidth = Number(node?.size?.[0]);
        const innerWidth = Number.isFinite(liveWidth) && liveWidth > 52
            ? liveWidth - 52 : (width || 220) - left * 2;
        const boxWidth = Math.max(80, innerWidth);
        const centerY = y + h * 0.5;
        const toggleWidth = h * 1.45;
        this.y = y;
        this.last_y = y;
        ctx.save();
        ctx.beginPath();
        ctx.roundRect(left, y, boxWidth, h, [h * 0.5]);
        ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
        ctx.fill();
        ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
        ctx.stroke();
        ctx.fillStyle = this.enabled ? "#89B" : "#777";
        ctx.beginPath();
        ctx.roundRect(left + 5, y + 5, toggleWidth - 10, h - 10, [h * 0.5]);
        ctx.fill();
        ctx.fillStyle = "#DDD";
        ctx.beginPath();
        ctx.arc(left + (this.enabled ? toggleWidth - h * 0.5 : h * 0.5), centerY,
            h * 0.27, 0, Math.PI * 2);
        ctx.fill();
        if (!this.enabled) ctx.globalAlpha = app.canvas.editor_alpha * 0.45;
        ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || "#999";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(this.label, left + toggleWidth + 5, centerY);
        const valueLeft = left + toggleWidth + 52;
        const valueWidth = boxWidth - toggleWidth - 62;
        ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
        ctx.textAlign = "right";
        ctx.fillText(fitText(ctx, this.value, valueWidth), left + boxWidth - 9, centerY);
        ctx.restore();
    }

    mouse(event, pos, node) {
        if (event.type !== "pointerdown") return false;
        const toggleLimit = 15 + LiteGraph.NODE_WIDGET_HEIGHT * 1.45;
        if (pos[0] <= toggleLimit) {
            if (this.toggleWidget) this.toggleWidget.value = !this.enabled;
            console.debug("[ED-UI] LoRA Plot row toggled", {
                node: node.id, index: this.index, enabled: this.enabled,
            });
        } else {
            openChoices(event, this.options?.values, value => {
                this.value = value;
                console.debug("[ED-UI] LoRA Plot row selected", {
                    node: node.id, index: this.index, lora: value,
                });
                node.setDirtyCanvas(true, true);
            });
        }
        node.setDirtyCanvas(true, true);
        return true;
    }
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

function num(node, name, fallback) {
    const value = Number(widget(node, name)?.value);
    return Number.isFinite(value) ? value : fallback;
}

function defaults(node) {
    return {
        xFirst: num(node, "X_first_value", 0.0),
        xLast: num(node, "X_last_value", 1.0),
        yFirst: num(node, "Y_first_value", 0.0),
        yLast: num(node, "Y_last_value", 1.0),
    };
}

function addNumber(node, name, label, value) {
    const item = node.addWidget("number", name, Number(value), () => {}, {
        min: -10, max: 10, step: 0.01, serialize: true,
    });
    item.label = label;
    item.serialize = true;
    return item;
}

function setRangeLabels(node, index) {
    const labels = {
        [`scan_lora_x_first_strength_${index}`]: `L${index} X MStr 起`,
        [`scan_lora_x_last_strength_${index}`]: `L${index} X MStr 止`,
        [`scan_lora_y_first_strength_${index}`]: `L${index} Y CStr 起`,
        [`scan_lora_y_last_strength_${index}`]: `L${index} Y CStr 止`,
    };
    for (const [name, label] of Object.entries(labels)) {
        const item = widget(node, name);
        if (item) item.label = label;
    }
}

// Rows already present in a saved workflow are restored by ComfyUI as normal
// combo/toggle widgets. New rows use PlotLoraRowWidget, so without this
// conversion row 1 keeps the raw `scan_lora_name_1` label while row 2 does
// not. Upgrade in place and preserve the serialized value/options.
function upgradeExistingRow(node, index) {
    const selector = widget(node, `scan_lora_name_${index}`);
    const toggle = widget(node, `scan_lora_${index}_toggle`);
    if (selector && selector.type !== "ed_plot_lora_row") {
        const row = new PlotLoraRowWidget(selector, toggle, node, index);
        row.value = selector.value ?? "None";
        row.options = selector.options || { values: ["None"] };
        row.label = `LoRA ${index}`;
        selector.label = "";
        const at = node.widgets.indexOf(selector);
        if (at >= 0) node.widgets[at] = row;
        console.debug("[ED-UI] upgraded restored LoRA Plot row", {
            node: node.id, index, lora: row.value,
        });
    } else if (selector) {
        selector.label = "";
        selector.labelText = `LoRA ${index}`;
    }
    hideWidget(toggle);
    setRangeLabels(node, index);
}

function addRow(node, index, saved = {}) {
    const base = { ...defaults(node), ...saved };
    const combo = node.addWidget("combo", `scan_lora_name_${index}`, base.name ?? "None",
        () => {}, { values: connectedStackNames(node) || ["None"], serialize: true });
    // The backend name is retained for graph serialization, but the visible
    // label is supplied by PlotLoraRowWidget.  This prevents the raw
    // scan_lora_name_N title from being drawn on top of the selected model.
    combo.label = "";
    const toggle = node.addWidget("toggle", `scan_lora_${index}_toggle`,
        base.toggle ?? true, () => {}, { serialize: true });
    const row = new PlotLoraRowWidget(combo, toggle, node, index);
    const comboIndex = node.widgets.indexOf(combo);
    if (comboIndex >= 0) node.widgets[comboIndex] = row;
    hideWidget(toggle);
    addNumber(node, `scan_lora_x_first_strength_${index}`, `L${index} MStr 起`, base.xFirst);
    addNumber(node, `scan_lora_x_last_strength_${index}`, `L${index} MStr 止`, base.xLast);
    addNumber(node, `scan_lora_y_first_strength_${index}`, `L${index} CStr 起`, base.yFirst);
    addNumber(node, `scan_lora_y_last_strength_${index}`, `L${index} CStr 止`, base.yLast);
    console.debug("[ED-UI] LoRA Plot row created", { node: node.id, index, lora: row.value });
}

function removeRow(node, index) {
    const row = rowWidgets(node, index);
    for (const item of [row.yLast, row.yFirst, row.xLast, row.xFirst, row.toggle, row.selector]) {
        removeWidgetSafe(node, item);
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
    for (let index = 1; index <= count; index += 1) upgradeExistingRow(node, index);
    const width = node.size?.[0] || 220;
    const computed = typeof node.computeSize === "function" ? node.computeSize() : [width, 140];
    node.setSize?.([width, Math.max(140, computed[1] || 0)]);
    node.setDirtyCanvas(true, true);
    return count;
}

function hideGlobalRanges(node) {
    for (const name of GLOBAL_RANGES) hideWidget(widget(node, name));
}

function restoreSaved(node) {
    if (node.__edPlotRowsRestored) return;
    const saved = node.__edPlotSavedValues;
    const countWidget = widget(node, "lora_count");
    let count = Number(countWidget?.value ?? 1);
    const rows = [];
    if (Array.isArray(saved)) {
        // Current base layout is 7 values: count, X/Y batch counts and the
        // four hidden global fallback ranges. New rows use 6 values.
        if (saved.length >= 7 && Number.isFinite(Number(saved[0]))) {
            count = Number(saved[0]);
            const fallback = defaults(node);
            const width = saved.length >= 7 + count * 6 ? 6 : 2;
            let offset = 7;
            for (let i = 0; i < count; i += 1) {
                const row = {
                    name: saved[offset], toggle: saved[offset + 1],
                    xFirst: fallback.xFirst, xLast: fallback.xLast,
                    yFirst: fallback.yFirst, yLast: fallback.yLast,
                };
                if (width === 6) {
                    row.xFirst = saved[offset + 2] ?? row.xFirst;
                    row.xLast = saved[offset + 3] ?? row.xLast;
                    row.yFirst = saved[offset + 4] ?? row.yFirst;
                    row.yLast = saved[offset + 5] ?? row.yLast;
                }
                rows.push(row);
                offset += width;
            }
        } else if (saved.length >= 13 && typeof saved[0] === "string") {
            // Historical Plot layout migration.
            count = saved[1] && saved[1] !== "None" ? 1 : 0;
            const values = {
                X_batch_count: saved[4], X_first_value: saved[8], X_last_value: saved[9],
                Y_batch_count: saved[10], Y_first_value: saved[11], Y_last_value: saved[12],
            };
            for (const [name, value] of Object.entries(values)) {
                const item = widget(node, name);
                if (item && value !== undefined) item.value = value;
            }
            const fallback = defaults(node);
            if (count) rows.push({ name: saved[1], toggle: true, ...fallback });
            console.debug("[ED-UI] migrated historical LoRA Plot widgets", { node: node.id });
        }
    }
    if (!Number.isFinite(count)) count = 0;
    if (countWidget) countWidget.value = count;
    ensureRows(node, count);
    rows.forEach((savedRow, offset) => {
        const row = rowWidgets(node, offset + 1);
        if (row.selector && savedRow.name !== undefined) row.selector.value = savedRow.name;
        if (row.toggle && savedRow.toggle !== undefined) row.toggle.value = savedRow.toggle;
        if (row.xFirst) row.xFirst.value = Number(savedRow.xFirst ?? row.xFirst.value);
        if (row.xLast) row.xLast.value = Number(savedRow.xLast ?? row.xLast.value);
        if (row.yFirst) row.yFirst.value = Number(savedRow.yFirst ?? row.yFirst.value);
        if (row.yLast) row.yLast.value = Number(savedRow.yLast ?? row.yLast.value);
    });
    hideGlobalRanges(node);
    refreshChoices(node);
    node.__edPlotRowsRestored = true;
}

function initialize(node) {
    if (!isPlot(node) || node.__edPlotDynamicInitialized) return;
    node.__edPlotDynamicInitialized = true;
    node.serialize_widgets = true;
    hideGlobalRanges(node);
    const count = widget(node, "lora_count");
    if (count) {
        const original = count.callback;
        count.callback = function(value) {
            const result = original?.apply(this, arguments);
            const current = countValue(value, count.value);
            ensureRows(node, current);
            refreshChoices(node);
            console.debug("[ED-UI] LoRA Plot count changed", { node: node.id, count: current });
            return result;
        };
    }
    const previousWidgetChanged = node.onWidgetChanged;
    node.onWidgetChanged = function(name, value, changedWidget) {
        const result = previousWidgetChanged?.apply(this, arguments);
        const widgetName = typeof name === "string" ? name : name?.name ?? changedWidget?.name;
        if (widgetName === "lora_count" && !this.__edPlotSyncing) {
            this.__edPlotSyncing = true;
            try {
                ensureRows(this, value ?? widget(this, "lora_count")?.value);
                refreshChoices(this);
            } finally { this.__edPlotSyncing = false; }
        } else if (typeof widgetName === "string" && widgetName.startsWith("scan_lora_name_")) {
            refreshChoices(this);
            this.setDirtyCanvas(true, true);
        }
        return result;
    };
    const previousConnections = node.onConnectionsChange;
    node.onConnectionsChange = function() {
        const result = previousConnections?.apply(this, arguments);
        refreshChoices(this);
        return result;
    };
    const previousDraw = node.onDrawForeground;
    node.onDrawForeground = function(ctx) {
        if (!this.__edPlotSyncing) {
            // ComfyUI may rebuild widget options during a drag/configure
            // cycle. Re-apply the hidden flags before measuring the node.
            hideGlobalRanges(this);
            const desired = Math.max(0, Math.min(MAX_ROWS, Number(widget(this, "lora_count")?.value ?? 0)));
            const actual = (this.widgets || []).map(item => {
                const match = ROW_RE.exec(item.name || "");
                return match ? Number(match[1]) : 0;
            }).filter(Boolean).reduce((max, index) => Math.max(max, index), 0);
            if (actual !== desired) {
                this.__edPlotSyncing = true;
                try { ensureRows(this, desired); } finally { this.__edPlotSyncing = false; }
            }
        }
        return previousDraw?.apply(this, arguments);
    };
    ensureRows(node, count?.value ?? 1);
    refreshChoices(node);
}

app.registerExtension({
    name: "ED.LoRAPlotDynamicStack",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!isPlot(nodeData) || nodeType.prototype.__edPlotPatched) return;
        nodeType.prototype.__edPlotPatched = true;
        const previous = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(info) {
            this.__edPlotSavedValues = info?.widgets_values;
            return previous?.apply(this, arguments);
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

// Keep choices synchronized when Power Loader rows are added later. This only
// mutates existing node-owned widgets; it never creates a floating menu.
setInterval(() => {
    for (const node of app.graph?._nodes || []) {
        if (isPlot(node)) refreshChoices(node);
    }
}, 1000);
