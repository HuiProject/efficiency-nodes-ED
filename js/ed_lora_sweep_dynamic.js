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
        clipFirst: widget(node, `scan_lora_clip_first_strength_${index}`),
        clipLast: widget(node, `scan_lora_clip_last_strength_${index}`),
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
    if (!item) return;
    if (!item.__edSweepHidden) {
        item.__edSweepOriginalType = item.type;
        item.__edSweepOriginalComputeSize = item.computeSize;
    }
    item.__edSweepHidden = true;
    // Match ComfyUI/ED's hidden-widget convention.  The frontend renders a
    // plain `hidden` type, leaving stale fields visible after node movement.
    item.type = "tschide";
    item.computeSize = () => [0, -4];
    item.hidden = true;
    item.options = item.options || {};
    item.options.hidden = true;
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

class SweepLoraRowWidget {
    constructor(combo, toggle, node, index) {
        this.name = combo.name;
        // The model name is the only text in this selector bar.  Keeping the
        // original `scan_lora_name_N` label (or an extra "LoRA N" caption)
        // causes it to overlap the selected filename after a pipe refresh.
        this.label = "";
        this.value = combo.value ?? "None";
        this.options = combo.options || { values: ["None"] };
        this.node = node;
        this.toggleWidget = toggle;
        this.index = index;
        this.type = "ed_sweep_lora_row";
        this.serialize = true;
        this.y = 0;
        this.last_y = 0;
    }

    get enabled() { return this.toggleWidget?.value !== false; }
    computeSize(width) { return [width || 220, LiteGraph.NODE_WIDGET_HEIGHT]; }
    serializeValue() { return this.value; }

    draw(ctx, node, width, y, height) {
        const h = height || LiteGraph.NODE_WIDGET_HEIGHT;
        const left = 15;
        // Use the node frame rather than LiteGraph's transient widget width.
        // During lora_pipe connection/selection the latter may be stale or
        // include combo-list padding, which made this row extend outside the
        // node. Native widgets occupy x=15 .. node.size[0]-15.
        const liveWidth = Number(node?.size?.[0]);
        const fallbackWidth = Number(width);
        const frameWidth = Number.isFinite(liveWidth) && liveWidth > 0
            ? liveWidth
            : (Number.isFinite(fallbackWidth) && fallbackWidth > 0 ? fallbackWidth : 220);
        const boxWidth = Math.max(80, frameWidth - left * 2);
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
        if (this.label) ctx.fillText(this.label, left + toggleWidth + 5, centerY);
        // With no caption, give the filename the same full value area as the
        // Plot row while retaining the toggle-to-value gutter.
        const valueWidth = boxWidth - toggleWidth - 22;
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
            console.debug("[ED-UI] Sweep row toggled", { node: node.id, index: this.index, enabled: this.enabled });
        } else {
            openChoices(event, this.options?.values, value => {
                this.value = value;
                console.debug("[ED-UI] Sweep row selected", { node: node.id, index: this.index, lora: value });
                node.setDirtyCanvas(true, true);
            });
        }
        node.setDirtyCanvas(true, true);
        return true;
    }
}

function upgradeExistingRow(node, index) {
    const selector = widget(node, `scan_lora_name_${index}`);
    const toggle = widget(node, `scan_lora_${index}_toggle`);
    if (selector && selector.type !== "ed_sweep_lora_row") {
        const row = new SweepLoraRowWidget(selector, toggle, node, index);
        row.value = selector.value ?? "None";
        row.options = selector.options || { values: ["None"] };
        selector.label = "";
        const at = node.widgets.indexOf(selector);
        if (at >= 0) node.widgets[at] = row;
        console.debug("[ED-UI] upgraded restored Sweep LoRA row", { node: node.id, index, lora: row.value });
    }
    if (selector?.type === "ed_sweep_lora_row") selector.label = "";
    hideWidget(toggle);
    const parts = rowWidgets(node, index);
    if (parts.first) parts.first.label = "Model S";
    if (parts.last) parts.last.label = "Model E";
    addMissingClipWidgets(node, index);
    const updated = rowWidgets(node, index);
    pairRangeWidgets(node, updated.first, updated.last, "Model S", "Model E");
    pairRangeWidgets(node, updated.clipFirst, updated.clipLast, "Clip S", "Clip E");
}

function showWidget(item) {
    if (!item?.__edSweepHidden) return;
    item.type = item.__edSweepOriginalType;
    item.computeSize = item.__edSweepOriginalComputeSize;
    item.hidden = false;
    if (item.options) item.options.hidden = false;
    item.__edSweepHidden = false;
}

function syncAxisVisibility(node) {
    const axis = String(widget(node, "axis")?.value || "X Model");
    const showModel = axis === "X Model" || axis === "Y Model" ||
        axis === "X Model and Clip" || axis === "Y Model and Clip" ||
        // Old saved value: X was the model axis.
        axis === "X";
    const showClip = axis === "X Clip" || axis === "Y Clip" ||
        axis === "X Model and Clip" || axis === "Y Model and Clip" ||
        // Old saved values: Y was the clip axis.
        axis === "Y";
    for (let index = 1; index <= MAX_ROWS; index++) {
        const parts = rowWidgets(node, index);
        if (!parts.name) continue;
        // The range pair is drawn by its first widget; its end widget must
        // stay hidden even when the pair itself is visible.
        const setPairVisibility = (first, last, visible) => {
            if (visible) {
                showWidget(first);
                hideWidget(last);
            } else {
                hideWidget(first);
                hideWidget(last);
            }
        };
        setPairVisibility(parts.first, parts.last, showModel);
        setPairVisibility(parts.clipFirst, parts.clipLast, showClip);
    }
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
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

function clampRangeValue(widgetItem, value) {
    const min = Number(widgetItem?.options?.min ?? -10);
    const max = Number(widgetItem?.options?.max ?? 10);
    return Math.max(min, Math.min(max, Number(value)));
}

function pairRangeWidgets(node, first, last, labelFirst, labelLast) {
    if (!first || !last) return;
    if (first.__edSweepRangePair) {
        first.__edSweepRangePair.end = last;
        first.__edSweepRangePair.labelFirst = labelFirst;
        first.__edSweepRangePair.labelLast = labelLast;
        hideWidget(last);
        return first;
    }
    const pair = { end: last, labelFirst, labelLast };
    first.__edSweepRangePair = pair;
    first.type = "ed_sweep_range_pair";
    first.label = "";
    first.serialize = true;
    first.serializeValue = function() { return Number(this.value ?? 0); };
    first.computeSize = width => [width || 220, LiteGraph.NODE_WIDGET_HEIGHT];
    first.draw = function(ctx, graphNode, width, y, height) {
        const h = height || LiteGraph.NODE_WIDGET_HEIGHT;
        const margin = 15;
        const frame = Number(graphNode?.size?.[0]) || Number(width) || 220;
        const total = Math.max(80, frame - margin * 2);
        const gap = 5;
        const half = Math.max(38, (total - gap) / 2);
        const values = [Number(this.value ?? 0), Number(pair.end?.value ?? 0)];
        const labels = [pair.labelFirst, pair.labelLast];
        ctx.save();
        for (let side = 0; side < 2; side += 1) {
            const x = margin + side * (half + gap);
            ctx.beginPath();
            ctx.roundRect(x, y, half, h, [h * 0.5]);
            ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
            ctx.fill();
            ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
            ctx.stroke();
            ctx.font = `${Math.max(9, h * 0.42)}px sans-serif`;
            ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || "#999";
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.fillText(fitText(ctx, labels[side], Math.max(18, half - 58)), x + 20, y + h * 0.5);
            ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
            ctx.textAlign = "right";
            ctx.font = `${Math.max(10, h * 0.5)}px sans-serif`;
            ctx.fillText(Number(values[side]).toFixed(2), x + half - 19, y + h * 0.5);
            ctx.textAlign = "center";
            ctx.fillText("−", x + 9, y + h * 0.5);
            ctx.fillText("+", x + half - 8, y + h * 0.5);
        }
        ctx.restore();
    };
    first.mouse = function(event, pos, graphNode) {
        if (event.type !== "pointerdown") return false;
        const margin = 15;
        const frame = Number(graphNode?.size?.[0]) || 220;
        const total = Math.max(80, frame - margin * 2);
        const gap = 5;
        const half = Math.max(38, (total - gap) / 2);
        const relative = Number(pos?.[0] ?? 0) - margin;
        const side = relative > half + gap ? 1 : 0;
        const localX = side ? relative - half - gap : relative;
        const target = side ? pair.end : this;
        if (!target) return true;
        const current = Number(target.value ?? 0);
        if (localX <= 18) {
            target.value = clampRangeValue(target, Math.round((current - 0.05) * 100) / 100);
        } else if (localX >= half - 18) {
            target.value = clampRangeValue(target, Math.round((current + 0.05) * 100) / 100);
        } else {
            app.canvas?.prompt?.("Value", current, value => {
                const parsed = Number(value);
                if (Number.isFinite(parsed)) target.value = clampRangeValue(target, parsed);
                graphNode.setDirtyCanvas(true, true);
            }, event);
        }
        graphNode.setDirtyCanvas(true, true);
        return true;
    };
    hideWidget(last);
    return first;
}

function addRow(node, index, values = {}) {
    const choices = connectedStackNames(node) || ["None"];
    const name = node.addWidget("combo", `scan_lora_name_${index}`,
        values.name ?? "None", () => {}, { values: choices, serialize: true });
    name.label = "";
    const toggle = node.addWidget("toggle", `scan_lora_${index}_toggle`,
        values.toggle ?? true, () => {}, { serialize: true });
    const row = new SweepLoraRowWidget(name, toggle, node, index);
    const nameIndex = node.widgets.indexOf(name);
    if (nameIndex >= 0) node.widgets[nameIndex] = row;
    hideWidget(toggle);
    const first = node.addWidget("number", `scan_lora_first_strength_${index}`,
        Number(values.first ?? 1.0), () => {}, { min: -10, max: 10, step: 0.01, serialize: true });
    const last = node.addWidget("number", `scan_lora_last_strength_${index}`,
        Number(values.last ?? 1.0), () => {}, { min: -10, max: 10, step: 0.01, serialize: true });
    first.label = "Model S";
    last.label = "Model E";
    const clipFirst = node.addWidget("number", `scan_lora_clip_first_strength_${index}`,
        Number(values.clipFirst ?? values.first ?? 1.0), () => {},
        { min: -10, max: 10, step: 0.01, serialize: true });
    const clipLast = node.addWidget("number", `scan_lora_clip_last_strength_${index}`,
        Number(values.clipLast ?? values.last ?? 1.0), () => {},
        { min: -10, max: 10, step: 0.01, serialize: true });
    clipFirst.label = "Clip S";
    clipLast.label = "Clip E";
    pairRangeWidgets(node, first, last, "Model S", "Model E");
    pairRangeWidgets(node, clipFirst, clipLast, "Clip S", "Clip E");
    for (const item of [name, toggle, first, last, clipFirst, clipLast]) {
        if (item) item.serialize = true;
    }
    console.debug("[ED-UI] Sweep row created", { node: node.id, index, lora: name?.value });
}

function insertAfter(node, anchor, item) {
    if (!anchor || !item || !Array.isArray(node.widgets)) return;
    const current = node.widgets.indexOf(item);
    if (current < 0) return;
    node.widgets.splice(current, 1);
    const anchorIndex = node.widgets.indexOf(anchor);
    node.widgets.splice(anchorIndex < 0 ? node.widgets.length : anchorIndex + 1, 0, item);
}

function addMissingClipWidgets(node, index) {
    const parts = rowWidgets(node, index);
    if (!parts.last || (parts.clipFirst && parts.clipLast)) return;
    // Migrate a pre-CLIP row in place. The new controls are node-owned and
    // serialize with the same row, so the old workflow needs no rewiring.
    const clipFirstValue = Number(parts.first?.value ?? 1.0);
    const clipLastValue = Number(parts.last?.value ?? 1.0);
    const clipFirst = parts.clipFirst || node.addWidget(
        "number", `scan_lora_clip_first_strength_${index}`, clipFirstValue,
        () => {}, { min: -10, max: 10, step: 0.01, serialize: true }
    );
    const clipLast = parts.clipLast || node.addWidget(
        "number", `scan_lora_clip_last_strength_${index}`, clipLastValue,
        () => {}, { min: -10, max: 10, step: 0.01, serialize: true }
    );
    clipFirst.label = "Clip S";
    clipLast.label = "Clip E";
    clipFirst.serialize = true;
    clipLast.serialize = true;
    insertAfter(node, parts.last, clipLast);
    insertAfter(node, parts.last, clipFirst);
    console.debug("[ED-UI] migrated Sweep CLIP controls", {
        node: node.id, index, clipFirst: clipFirst.value, clipLast: clipLast.value,
    });
}

function removeRow(node, index) {
    const parts = rowWidgets(node, index);
    // Remove in reverse order so widget indexes remain stable.
    for (const item of [parts.clipLast, parts.clipFirst, parts.last, parts.first, parts.toggle, parts.name]) {
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
    for (let index = 1; index <= count; index++) upgradeExistingRow(node, index);
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
    let legacyFirst = 1.0;
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

    // Current format: base widgets occupy indexes 0..5, followed by six
    // values per row: name, toggle, model first/last, clip first/last.
    if (!legacyName && hasCompactCount && Array.isArray(saved) && saved.length > 6) {
        let offset = 6;
        const rowWidth = saved.length >= 6 + count * 6 ? 6 : 4;
        for (let index = 1; index <= count; index++) {
            const parts = rowWidgets(node, index);
            if (!parts.name) continue;
            if (saved[offset] !== undefined) parts.name.value = saved[offset];
            if (saved[offset + 1] !== undefined) parts.toggle.value = saved[offset + 1];
            if (saved[offset + 2] !== undefined) parts.first.value = saved[offset + 2];
            if (saved[offset + 3] !== undefined) parts.last.value = saved[offset + 3];
            if (rowWidth >= 6) {
                if (saved[offset + 4] !== undefined) parts.clipFirst.value = saved[offset + 4];
                if (saved[offset + 5] !== undefined) parts.clipLast.value = saved[offset + 5];
            } else {
                // Old rows had one pair of strengths.  Keep CLIP behavior
                // identical until the user explicitly changes its fields.
                if (parts.clipFirst) parts.clipFirst.value = parts.first?.value ?? 1.0;
                if (parts.clipLast) parts.clipLast.value = parts.last?.value ?? 1.0;
            }
            offset += rowWidth;
        }
    } else if (count === 1 && legacyName && legacyName !== "None") {
        const parts = rowWidgets(node, 1);
        parts.name.value = legacyName;
        parts.first.value = legacyFirst;
        parts.last.value = legacyLast;
        if (parts.clipFirst) parts.clipFirst.value = legacyFirst;
        if (parts.clipLast) parts.clipLast.value = legacyLast;
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
    const axisWidget = widget(node, "axis");
    if (axisWidget) {
        const originalAxisCallback = axisWidget.callback;
        axisWidget.callback = function (value) {
            originalAxisCallback?.apply(this, arguments);
            syncAxisVisibility(node);
            console.debug("[ED-UI] Sweep axis changed", { node: node.id, axis: this.value ?? value });
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
        } else if (widgetName === "axis") {
            syncAxisVisibility(this);
        }
        return result;
    };

    // Some 1.47.x editor paths update the widget value without dispatching the
    // legacy callback or node hook. Reconcile once per draw so stale rows from
    // an older tab/workflow cannot remain visible or reach graphToPrompt.
    const originalDrawForeground = node.onDrawForeground;
    node.onDrawForeground = function (ctx) {
        if (!this.__edSweepSyncing) {
            hideWidget(widget(this, "target_lora"));
            hideWidget(widget(this, "first_strength"));
            hideWidget(widget(this, "last_strength"));
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
    syncAxisVisibility(node);

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
