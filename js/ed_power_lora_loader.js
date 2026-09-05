import { app } from "../../scripts/app.js";

// ED-owned Power Lora Loader UI.  The backend accepts one dictionary per
// `lora_N` wildcard input: {on, lora, strength, strengthTwo}.  Keeping the
// editor here makes the ED node usable when rgthree is disabled and gives
// every row an explicit Model/Clip strength control.
const NODE_NAME = "Power Lora Loader 💬ED (LORA_STACK)";
const MAX_ROWS = 50;
const H = () => LiteGraph.NODE_WIDGET_HEIGHT;
let loraChoicesPromise = null;

function isPowerLoader(data) {
    return [data?.name, data?.comfyClass, data?.type, data?.title,
        data?.properties?.["Node name for S&R"]]
        .some(value => String(value || "") === NODE_NAME);
}

function fitText(ctx, value, width) {
    let text = String(value || "None");
    if (ctx.measureText(text).width <= width) return text;
    while (text.length > 1 && ctx.measureText(`${text}…`).width > width) {
        text = text.slice(0, -1);
    }
    return `${text}…`;
}

function roundedBox(ctx, x, y, width, height) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, [height * 0.5]);
    ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
    ctx.fill();
    ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
    ctx.stroke();
}

function togglePart(ctx, x, y, height, enabled) {
    const width = height * 1.45;
    ctx.fillStyle = enabled ? "#89B" : "#777";
    ctx.beginPath();
    ctx.roundRect(x + 5, y + 5, width - 10, height - 10, [height * 0.5]);
    ctx.fill();
    ctx.fillStyle = "#DDD";
    ctx.beginPath();
    ctx.arc(x + (enabled ? width - height * 0.5 : height * 0.5),
        y + height * 0.5, height * 0.27, 0, Math.PI * 2);
    ctx.fill();
    return width;
}

function numberPart(ctx, x, y, height, value, label) {
    const width = 70;
    const arrow = 16;
    ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || "#999";
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.font = `${Math.max(9, height * 0.42)}px sans-serif`;
    ctx.fillText(label, x + width * 0.5, y - 1);
    ctx.fillStyle = LiteGraph.WIDGET_BGCOLOR;
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, [height * 0.5]);
    ctx.fill();
    ctx.strokeStyle = LiteGraph.WIDGET_OUTLINE_COLOR;
    ctx.stroke();
    ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `${Math.max(10, height * 0.5)}px sans-serif`;
    ctx.fillText("−", x + arrow * 0.5, y + height * 0.5);
    ctx.fillText(Number(value ?? 1).toFixed(2), x + width * 0.5, y + height * 0.5);
    ctx.fillText("+", x + width - arrow * 0.5, y + height * 0.5);
    return { x, width, dec: [x, arrow], value: [x + arrow, width - arrow * 2], inc: [x + width - arrow, arrow] };
}

function normalizeValue(value) {
    const source = value && typeof value === "object" ? value : {};
    const strength = Number.isFinite(Number(source.strength)) ? Number(source.strength) : 1;
    const clip = source.strengthTwo == null ? strength : Number(source.strengthTwo);
    return {
        on: source.on !== false,
        lora: source.lora || "None",
        strength,
        strengthTwo: Number.isFinite(clip) ? clip : strength,
    };
}

async function getLoraChoices() {
    if (!loraChoicesPromise) {
        loraChoicesPromise = fetch("/object_info")
            .then(response => response.ok ? response.json() : {})
            .then(info => {
                const node = info?.["LoRA Stacker 💬ED"] || info?.["LoRA Stacker"];
                const values = node?.input?.required?.lora_name_1?.[0];
                return Array.isArray(values) ? ["None", ...values.filter(v => v !== "None")] : ["None"];
            })
            .catch(error => {
                console.warn("[ED-UI] Power Loader lora list unavailable", error);
                return ["None"];
            });
    }
    return loraChoicesPromise;
}

function chooseLora(event, choices, callback) {
    new LiteGraph.ContextMenu(choices || ["None"], {
        event,
        scale: Math.max(1, app.canvas?.ds?.scale ?? 1),
        className: "dark",
        callback: value => typeof value === "string" && callback(value),
    });
}

class EdPowerHeaderWidget {
    constructor() {
        this.name = "ed_power_lora_header";
        this.type = "ed_power_lora_header";
        this.value = { type: "PowerLoraLoaderHeaderWidget" };
        this.serialize = false;
        this.computeSize = width => [width || 280, H()];
    }

    draw(ctx, node, width, y, height) {
        if (!(node.__edPowerRows || []).length) return;
        const margin = 10;
        const right = Number(node.size?.[0]) || Number(width) || 280;
        ctx.save();
        ctx.fillStyle = LiteGraph.WIDGET_SECONDARY_TEXT_COLOR || "#999";
        ctx.textBaseline = "middle";
        ctx.textAlign = "left";
        ctx.fillText("Toggle All", margin + H() * 1.45 + 5, y + height * 0.5);
        ctx.textAlign = "center";
        ctx.fillText("Model", right - 10 - 70 - 70 - 8, y + height * 0.5);
        ctx.fillText("Clip", right - 10 - 70, y + height * 0.5);
        ctx.restore();
    }

    mouse(event, pos, node) {
        if (event.type !== "pointerdown") return false;
        for (const row of node.__edPowerRows || []) row.value.on = !(node.__edPowerAllOn ?? true);
        node.__edPowerAllOn = !(node.__edPowerAllOn ?? true);
        node.setDirtyCanvas(true, true);
        return true;
    }
}

class EdPowerLoraRowWidget {
    constructor(name, value) {
        this.name = name;
        this.type = "ed_power_lora_row";
        this.serialize = true;
        this.value = normalizeValue(value);
        this.hit = {};
        this.y = 0;
        this.last_y = 0;
    }

    computeSize(width) { return [width || 280, H() + 8]; }

    serializeValue() { return normalizeValue(this.value); }

    draw(ctx, node, width, y, height) {
        const h = height || H();
        const margin = 10;
        const frame = Number(node?.size?.[0]) || Number(width) || 280;
        const boxWidth = Math.max(120, frame - margin * 2);
        const mid = y + h * 0.5;
        this.y = y;
        this.last_y = y;
        ctx.save();
        roundedBox(ctx, margin, y, boxWidth, h);
        const toggleWidth = togglePart(ctx, margin, y, h, this.value.on);
        const left = margin + toggleWidth + 8;
        const clipX = margin + boxWidth - 70;
        const modelX = clipX - 78;
        this.hit.toggle = [margin, toggleWidth];
        this.hit.clip = numberPart(ctx, clipX, y, h, this.value.strengthTwo, "Clip");
        this.hit.model = numberPart(ctx, modelX, y, h, this.value.strength, "Strength");
        ctx.globalAlpha = this.value.on ? 1 : (app.canvas?.editor_alpha || 1) * 0.45;
        ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.font = `${Math.max(10, h * 0.55)}px sans-serif`;
        this.hit.lora = [left, Math.max(20, modelX - left - 5)];
        ctx.fillText(fitText(ctx, this.value.lora, this.hit.lora[1]), left, mid);
        ctx.restore();
    }

    mouse(event, pos, node) {
        if (event.type !== "pointerdown") return false;
        const x = Number(pos?.[0]) || 0;
        const hit = this.hit;
        if (x >= hit.toggle?.[0] && x <= hit.toggle[0] + hit.toggle[1]) {
            this.value.on = !this.value.on;
        } else if (x >= hit.lora?.[0] && x <= hit.lora[0] + hit.lora[1]) {
            getLoraChoices().then(choices => chooseLora(event, choices, value => {
                this.value.lora = value;
                node.setDirtyCanvas(true, true);
            }));
        } else if (x >= hit.model?.x && x <= hit.model.x + hit.model.width) {
            this.adjustNumber("strength", hit.model, x, event, node);
        } else if (x >= hit.clip?.x && x <= hit.clip.x + hit.clip.width) {
            this.adjustNumber("strengthTwo", hit.clip, x, event, node);
        }
        node.setDirtyCanvas(true, true);
        return true;
    }

    adjustNumber(field, area, x, event, node) {
        const current = Number(this.value[field] ?? 1);
        if (x <= area.x + area.dec[1]) this.value[field] = Math.round((current - 0.05) * 100) / 100;
        else if (x >= area.x + area.width - area.inc[1]) this.value[field] = Math.round((current + 0.05) * 100) / 100;
        else app.canvas?.prompt?.("Value", current, value => {
            const parsed = Number(value);
            if (Number.isFinite(parsed)) this.value[field] = parsed;
            node.setDirtyCanvas(true, true);
        }, event);
    }
}

class EdPowerAddButtonWidget {
    constructor() {
        this.name = "ed_power_lora_add";
        this.type = "ed_power_lora_add";
        this.serialize = false;
        this.computeSize = width => [width || 280, H()];
    }

    draw(ctx, node, width, y, height) {
        const margin = 10;
        const frame = Number(node?.size?.[0]) || Number(width) || 280;
        ctx.save();
        roundedBox(ctx, margin, y, Math.max(120, frame - margin * 2), height || H());
        ctx.fillStyle = LiteGraph.WIDGET_TEXT_COLOR;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("➕ Add Lora", frame * 0.5, y + (height || H()) * 0.5);
        ctx.restore();
    }

    mouse(event, pos, node) {
        if (event.type !== "pointerdown") return false;
        getLoraChoices().then(choices => chooseLora(event, choices, value => {
            if (value !== "None") node.addEdLoraRow({ lora: value, on: true, strength: 1, strengthTwo: 1 });
        }));
        return true;
    }
}

function addCustom(node, custom) {
    custom.node = node;
    if (typeof node.addCustomWidget === "function") node.addCustomWidget(custom);
    else node.widgets.push(custom);
    return custom;
}

function installNodeMethods(nodeType) {
    if (nodeType.prototype.__edPowerLoaderPatched) return;
    nodeType.prototype.__edPowerLoaderPatched = true;
    const previousConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function(info) {
        this.__edPowerSavedValues = info?.widgets_values;
        return previousConfigure?.apply(this, arguments);
    };
    const previousSize = nodeType.prototype.computeSize;
    nodeType.prototype.computeSize = function() {
        const result = previousSize?.apply(this, arguments) || [280, 100];
        return [Math.max(280, Number(result[0]) || 280), result[1]];
    };
}

function initialize(node) {
    if (!isPowerLoader(node) || node.__edPowerInitialized) return;
    node.__edPowerInitialized = true;
    node.serialize_widgets = true;

    // If rgthree is enabled it may already have installed its own
    // PowerLoraLoaderWidget on this compatibility alias. Do not add a second
    // set of rows; request rgthree's separate Model/Clip presentation instead
    // and leave ownership with that already-created widget set.
    if (typeof node.addNewLoraWidget === "function" ||
        (node.widgets || []).some(item => item?.constructor?.name === "PowerLoraLoaderWidget")) {
        node.properties = node.properties || {};
        node.properties["Show Strengths"] = "Separate Model & Clip";
        node.__edPowerUsingExistingUI = true;
        console.debug("[ED-UI] Power Loader existing UI detected; enabled Model/Clip strengths", { node: node.id });
        return;
    }

    node.__edPowerRows = [];
    node.addEdLoraRow = value => {
        if (node.__edPowerRows.length >= MAX_ROWS) return;
        const row = new EdPowerLoraRowWidget(`lora_${node.__edPowerRows.length + 1}`, value);
        node.__edPowerRows.push(row);
        const addIndex = node.widgets.indexOf(node.__edPowerAddButton);
        if (addIndex >= 0) node.widgets.splice(addIndex, 0, row);
        else addCustom(node, row);
        node.setSize?.([Math.max(280, Number(node.size?.[0]) || 280), node.computeSize?.()[1] || 100]);
        node.setDirtyCanvas(true, true);
        console.debug("[ED-UI] Power Loader row added", { node: node.id, index: node.__edPowerRows.length, lora: row.value.lora });
        return row;
    };
    addCustom(node, new EdPowerHeaderWidget());
    const saved = Array.isArray(node.__edPowerSavedValues) ? node.__edPowerSavedValues : [];
    for (const value of saved) {
        if (value && typeof value === "object" && typeof value.lora === "string") node.addEdLoraRow(value);
    }
    node.__edPowerAddButton = addCustom(node, new EdPowerAddButtonWidget());
    node.setDirtyCanvas(true, true);
}

function restoreSavedRows(node) {
    if (node.__edPowerUsingExistingUI || !node.__edPowerInitialized ||
        node.__edPowerRows?.length || !Array.isArray(node.__edPowerSavedValues)) return;
    for (const value of node.__edPowerSavedValues) {
        if (value && typeof value === "object" && typeof value.lora === "string") {
            node.addEdLoraRow(value);
        }
    }
    node.setDirtyCanvas(true, true);
}

app.registerExtension({
    name: "ED.PowerLoraLoader",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (isPowerLoader(nodeData)) installNodeMethods(nodeType);
    },
    nodeCreated(node) { initialize(node); },
    async afterConfigureGraph() {
        for (const node of app.graph?._nodes || []) {
            initialize(node);
            restoreSavedRows(node);
        }
    },
});
