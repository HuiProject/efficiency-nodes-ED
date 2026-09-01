import { app } from "../../scripts/app.js";
// import { toRaw } from "vue";

import { toggleWidget, findWidgetByName, updateNodeHeight, flashWidget } from "./node_options/common/utils.js";

import { edComboWidget_Init, ED_COMBO_NODES } from "./ed_comboWidget.js"
import { handleGetBooruTag, getBooruTagRegionalScript_Init } from "./ed_getBooruTag.js"
import { edAppearance_Init } from "./ed_appearance.js"

let dynamicWidgets_initialized = false;

const NODE_WIDGET_HANDLERS = {
    "Efficient Loader 💬ED": {
        'paint_mode': handleEfficientLoaderPaintMode_ED,
        'ckpt_name': handleEfficientLoaderFluxMode_ED
    },
    "KSampler (Efficient) 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "KSampler Text 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "Load Image 💬ED": {
        'upscale_method': handleLoadImage_ED
    },
    "FaceDetailer 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "MaskDetailer 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "Detailer (SEGS) 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "Embedding Stacker 💬ED": {
        'positive_embeddings_count': handleEmbeddingStacker,
        'negative_embeddings_count': handleEmbeddingStacker
    },
    "Ultimate SD Upscale 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED,
        'set_tile_size_from': handleUltimateSDUpscalerTileSize_ED
    },
    "LoRA Stacker 💬ED": {
        'input_mode': handleLoRAStackerEDInputMode,
        'lora_count': handleLoRAStackerEDLoraCount
    },
    "XY Input: LoRA Sweep 💬ED": {
        'scan_lora_count': handleEDLoraSweepCount
    },
    "SUPIR Sampler 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "Refiner Script 💬ED": {
        'set_seed_cfg_sampler': handleEfficientSamplerSetSeed_ED
    },
    "Regional Script 💬ED": {
        'url': handleGetBooruTag
    },
    "Get Booru Tag 💬ED": {
        'url': handleGetBooruTag
    },
};

/////////////////////////////////////////////////////////////////////////// ED

function getNodeFromLink(node, linkId, from = "") {
    const linkInfo = app.graph.links[linkId];
    const id = from === "origin" ? linkInfo.origin_id : linkInfo.target_id;
    return node.graph.getNodeById(id);
}

function isMatchingNode(node, nodeType) {
    return node.type?.includes(nodeType);
}

export function findPreviousNode(node, targetType) {
    if (!node) return null;

    for (const port of node.inputs) {
        const link = port.link;
        if (!link) continue;

        const connectedNode = getNodeFromLink(node, link, "origin");
        if (!connectedNode) continue;

        // 원하는 타입 매칭 확인
        if (isMatchingNode(connectedNode, targetType)) {
            return connectedNode;
        }

    }
    return null;
}


function recursive_FindLinkedNode(node, nodeType) {

    function isContextNode(node) {
        return node.type && (node.type.includes('Context') || node.type === 'Wildcard Encode 💬ED' || node.type === 'TIPO Script 💬ED');
    }

    if (!node) return null;
    const links = node.outputs[0]?.links;
    if (!links) return null;

    for (const linkId of links) {
        const targetNode = getNodeFromLink(node, linkId);
        if (!targetNode) return null;

        if (isMatchingNode(targetNode, nodeType)) {
            return targetNode;
        }

        if (isContextNode(targetNode)) {
            return recursive_FindLinkedNode(targetNode, nodeType);
        }
    }

    return null;
}

// New function to handle widget visibility based on input_mode
function handleInputModeWidgetsVisibility(node, inputModeValue) {
    // Utility function to generate widget names up to a certain count
    function generateWidgetNames(baseName, count) {
        return Array.from({ length: count }, (_, i) => `${baseName}_${i + 1}`);
    }

    // Common widget groups
    // const batchWidgets = ["batch_path", "subdirectories", "batch_sort", "batch_max"];
    // const xbatchWidgets = ["X_batch_path", "X_subdirectories", "X_batch_sort", "X_batch_max"];
    // const ckptWidgets = [...generateWidgetNames("ckpt_name", 10)];
    // const clipSkipWidgets = [...generateWidgetNames("clip_skip", 10)];
    // const vaeNameWidgets = [...generateWidgetNames("vae_name", 10)];
    // const loraNameWidgets = [...generateWidgetNames("lora_name", 10)];
    const loraWtWidgets = [...generateWidgetNames("lora_wt", 10)];
    const modelStrWidgets = [...generateWidgetNames("model_str", 10)];
    const clipStrWidgets = [...generateWidgetNames("clip_str", 10)];
    // const xWidgets = ["X_batch_count", "X_first_value", "X_last_value"]
    // const yWidgets = ["Y_batch_count", "Y_first_value", "Y_last_value"]

    const nodeVisibilityMap = {
        "LoRA Stacker 💬ED": {
            "simple": [...modelStrWidgets, ...clipStrWidgets],
            "advanced": [...loraWtWidgets]
        },
    };

    const inputModeVisibilityMap = nodeVisibilityMap[node.comfyClass];

    if (!inputModeVisibilityMap || !inputModeVisibilityMap[inputModeValue]) return;

    // Reset all widgets to visible
    for (const key in inputModeVisibilityMap) {
        for (const widgetName of inputModeVisibilityMap[key]) {
            const widget = findWidgetByName(node, widgetName);
            toggleWidget(node, widget, true);
        }
    }

    // Hide the specific widgets for the current input_mode value
    for (const widgetName of inputModeVisibilityMap[inputModeValue]) {
        const widget = findWidgetByName(node, widgetName);
        toggleWidget(node, widget, false);
    }
}

// Handle multi-widget visibilities
function handleVisibility(node, widget, node_type) {
    const baseNamesMap = {
        "LoRA Stacker 💬ED": ["lora_name", "model_str", "clip_str", "lora_wt"],
        "Embedding Stacker 💬ED_pos": ["positive_embedding", "pos_weight"],
        "Embedding Stacker 💬ED_neg": ["negative_embedding", "neg_weight"]
    };
    const initValue = {
        "lora_name": "None",
        "model_str": 1,
        "clip_str": 1,
        "lora_wt": 1,
        "positive_embedding": "None",
        "pos_weight": 1,
        "negative_embedding": "None",
        "neg_weight": 1
    };

    function initWidgetVar(w) {
        const matchedKey = Object.keys(initValue).find(key => w.name.includes(key));
        if (matchedKey) {
            w.value = initValue[matchedKey];
        }
    }

    const countValue = widget.value;

    const baseNames = baseNamesMap[node_type];

    for (let i = 1; i <= 9; i++) {
        const widget_1 = findWidgetByName(node, `${baseNames[0]}_${i}`);
        const widget_2 = findWidgetByName(node, `${baseNames[1]}_${i}`);
        const widget_3 = (node_type === "LoRA Stacker 💬ED") ? findWidgetByName(node, `${baseNames[2]}_${i}`) : null;
        const widget_4 = (node_type === "LoRA Stacker 💬ED") ? findWidgetByName(node, `${baseNames[3]}_${i}`) : null;

        if (i <= countValue) {

            if (node_type === "LoRA Stacker 💬ED") {
                const inputModeValue = findWidgetByName(node, "input_mode").value;

                toggleWidget(node, widget_1, true);
                if (inputModeValue === "simple") {
                    toggleWidget(node, widget_2, false);   // model_str
                    toggleWidget(node, widget_3, false); // clip_str
                    toggleWidget(node, widget_4, true);  // lora_wt
                } else if (inputModeValue === "advanced") {
                    toggleWidget(node, widget_2, true);   // model_str
                    toggleWidget(node, widget_3, true);  // clip_str
                    toggleWidget(node, widget_4, false);   // lora_wt
                }
            } else if (node_type.includes("Embedding Stacker 💬ED")) {
                toggleWidget(node, widget_1, true);   // _embedding
                toggleWidget(node, widget_2, true);   // _weight
            }
        }
        else {
            toggleWidget(node, widget_1, false);
            if (widget_1.constructor.name === "EdToggleComboWidget") widget_1.toggle = true;
            initWidgetVar(widget_1);
            toggleWidget(node, widget_2, false);
            initWidgetVar(widget_2);
            if (widget_3) {
                toggleWidget(node, widget_3, false);
                initWidgetVar(widget_3);
            }
            if (widget_4) {
                toggleWidget(node, widget_4, false);
                initWidgetVar(widget_4);
            }
            const toggle_widget = findWidgetByName(node, `${baseNames[0]}_${i}_toggle`);
            if (toggle_widget) toggle_widget.value = true;
        }
    }
}

// In the main function where widgetLogic is called
function widgetLogic(node, widget) {
    // Retrieve the handler for the current node title and widget name
    const handler = NODE_WIDGET_HANDLERS[node.comfyClass]?.[widget.name];
    if (handler) {
        handler(node, widget);
    }
}

// Efficient Loader ED Paint Mode Handlers
function handleEfficientLoaderPaintMode_ED(node, widget) {
    const sampler_ed = recursive_FindLinkedNode(node, 'KSampler (Efficient) 💬ED')

    if (!sampler_ed?.toggleWidgetByProperty) return;

    const target_widget = findWidgetByName(sampler_ed, "denoise");
    let flashWidget_list = [];

    if (widget.value == '✍️ Txt2Img') {
        PREV_value.denoise = backupAndSet(target_widget, 1.0, flashWidget_list);
        sampler_ed.toggleWidgetByProperty(false);
    } else if (widget.value == '🎨 Inpaint(MaskDetailer)') {
        PREV_value.denoise = restoreIfMatch(target_widget, 1.0, PREV_value.denoise, flashWidget_list);
        sampler_ed.toggleWidgetByProperty(true);
    }
    else {
        PREV_value.denoise = restoreIfMatch(target_widget, 1.0, PREV_value.denoise, flashWidget_list);
        sampler_ed.toggleWidgetByProperty(false);
    }
    flashWidget(node, flashWidget_list);
}

let PREV_value = {
    denoise: 0.8,
    sdxl : { vae: null, clipSkip: null, cfg: null, sampler: null, scheduler: null },
	flux : { vae: null, clipSkip: null, cfg: null, sampler: null, scheduler: null },
	anima : { vae: null, clipSkip: null, cfg: null, sampler: null, scheduler: null },
};

// ----------------------
// Helper Functions
// ----------------------

// 값을 새로운 값으로 덮어쓰고, 기존 값을 반환 (백업용)
function backupAndSet(widget, newValue, flashWidgetList=[], prevValue=null) {
    if (!widget) return null;
	
	if (prevValue != null ) {
		if (widget.value != prevValue) {
			widget.value = prevValue;
			flashWidgetList.push(widget);
		}
		return prevValue;
	}
	
    if (widget.value === newValue) return widget.value; // 변화 없음	
    const oldVal = widget.value;
    widget.value = newValue;
    flashWidgetList.push(widget);
    return oldVal;
}

// widget.value가 특정 값과 같을 때만 이전 값으로 되돌림
function restoreIfMatch(widget, matchValue, prevValue, flashWidgetList = []) {
    if (!widget) return prevValue;
    if (widget.value === matchValue && widget.value != prevValue) {
        widget.value = prevValue;
        flashWidgetList.push(widget);
    }
    return prevValue;
}

function findVaeAndSave(wVae, wClipSkip, wCfg, wSampler, wScheduler) {
	if (!wVae) return;
	
	let prevType;	
	if (wVae.value === "🔌 ext model input")	{
		prevType = PREV_value.flux;
	} else if (contains(wVae.value, "anima") || contains(wVae.value, "qwen")) {
		prevType = PREV_value.anima;
	} else {
		prevType = PREV_value.sdxl;
	}
	
	prevType.vae = wVae.value;
	prevType.clipSkip = wClipSkip.value;
	prevType.cfg = wCfg.value;
	prevType.sampler =  wSampler.value;
	prevType.scheduler = wScheduler.value;	
}


// 텍스트에 특정 키워드 포함 여부 확인
function contains(text, keyword) {
    return text?.toLowerCase().includes(keyword);
}

// ----------------------
// Main Handler
// ----------------------
function handleEfficientLoaderFluxMode_ED(node, widget) {

    function changeStackerMode(node, mode = 0) {
        const loraStacker = findPreviousNode(node, "LoRA Stacker 💬ED");
        if (loraStacker) {
            loraStacker.mode = mode;

            const embeddingStacker = findPreviousNode(loraStacker, "Embedding Stacker 💬ED");
            if (embeddingStacker) {
                embeddingStacker.mode = mode;
            }
        }
    }

    if (!dynamicWidgets_initialized) return;

    const wClipSkip = findWidgetByName(node, "clip_skip");
    const wCfg = findWidgetByName(node, "cfg");
    const wVae = findWidgetByName(node, "vae_name");
    const wSampler = findWidgetByName(node, "sampler_name");
    const wScheduler = findWidgetByName(node, "scheduler");

    const fluxVae = wVae.options.values.find(v => contains(v, "flux"));
    const sdxlVae = wVae.options.values.find(v => contains(v, "sdxl_vae"));
	const animaVae = wVae.options.values.find(v => contains(v, "anima") || contains(v, "qwen"));

    if (widget.value === "🔌 ext model input") {
        // ------------------
        // Flux 모드
        // ------------------
        let flashWidgetList = [];
		
		//이전 값 backup
		findVaeAndSave(wVae, wClipSkip, wCfg, wSampler, wScheduler);
		
        PREV_value.flux.vae = backupAndSet(wVae, fluxVae, flashWidgetList, PREV_value.flux.vae);
        PREV_value.flux.clipSkip = backupAndSet(wClipSkip, 0, flashWidgetList, PREV_value.flux.clipSkip);
        PREV_value.flux.cfg = backupAndSet(wCfg, 1, flashWidgetList, PREV_value.flux.cfg);
        PREV_value.flux.sampler = backupAndSet(wSampler, "euler", flashWidgetList, PREV_value.flux.sampler);
        PREV_value.flux.scheduler = backupAndSet(wScheduler, "normal", flashWidgetList, PREV_value.flux.scheduler);

        changeStackerMode(node, 4);

        // 위젯 깜빡임 효과
        flashWidget(node, flashWidgetList);

    } else if (widget.value.includes("Anima")) {
        // ------------------
        // Anima 모드
        // ------------------
        let flashWidgetList = [];

		//이전 값 backup
		findVaeAndSave(wVae, wClipSkip, wCfg, wSampler, wScheduler);
		
        PREV_value.anima.vae = backupAndSet(wVae, animaVae, flashWidgetList, PREV_value.anima.vae);
        PREV_value.anima.clipSkip = backupAndSet(wClipSkip, 0, flashWidgetList, PREV_value.anima.clipSkip);
        PREV_value.anima.cfg = backupAndSet(wCfg, 5, flashWidgetList, PREV_value.anima.cfg);
        PREV_value.anima.sampler = backupAndSet(wSampler, "er_sde", flashWidgetList, PREV_value.anima.sampler);
        PREV_value.anima.scheduler = backupAndSet(wScheduler, "simple", flashWidgetList, PREV_value.anima.scheduler);

        changeStackerMode(node, 0);

        // 위젯 깜빡임 효과
        flashWidget(node, flashWidgetList);

    } else {
        // ------------------
        // 일반 모델 모드
        // ------------------
        let flashWidgetList = [];

		//이전 값 backup
		findVaeAndSave(wVae, wClipSkip, wCfg, wSampler, wScheduler);
		
        PREV_value.sdxl.vae = backupAndSet(wVae, sdxlVae, flashWidgetList, PREV_value.sdxl.vae);
        PREV_value.sdxl.clipSkip = backupAndSet(wClipSkip, -2, flashWidgetList, PREV_value.sdxl.clipSkip);
        PREV_value.sdxl.cfg = backupAndSet(wCfg, 5, flashWidgetList, PREV_value.sdxl.cfg);
        PREV_value.sdxl.sampler = backupAndSet(wSampler, "euler_ancestral", flashWidgetList, PREV_value.sdxl.sampler);
        PREV_value.sdxl.scheduler = backupAndSet(wScheduler, "normal", flashWidgetList, PREV_value.sdxl.scheduler);

        changeStackerMode(node, 0);

        // 위젯 깜빡임 효과
        flashWidget(node, flashWidgetList);
    }
}

// Sampler Set Seed ED Handlers
function handleEfficientSamplerSetSeed_ED(node, widget) {
    const opened = !(widget.value === "from context");

    toggleWidget(node, findWidgetByName(node, 'seed'), opened);
    toggleWidget(node, findWidgetByName(node, 'control_after_generate'), opened);
    toggleWidget(node, findWidgetByName(node, 'cfg'), opened);
    toggleWidget(node, findWidgetByName(node, 'sampler_name'), opened);
    toggleWidget(node, findWidgetByName(node, 'scheduler'), opened);
    //toggleWidget(node, findWidgetByName(node, 'batch_size'), opened);

    node.setDirtyCanvas(true, true);
}

// LoadImage ED Handlers
function handleLoadImage_ED(node, widget) {
    const opened = !(widget.value.includes("not upscale"));

    toggleWidget(node, findWidgetByName(node, 'width'), opened);
    toggleWidget(node, findWidgetByName(node, 'height'), opened);
    toggleWidget(node, findWidgetByName(node, 'keep_proportions'), opened);
}

// UltimateSDUpscaler ED Handlers
function handleUltimateSDUpscalerTileSize_ED(node, widget) {
    if (widget.value == 'Image size' || widget.value == 'Canvas size') {
        toggleWidget(node, findWidgetByName(node, 'tile_width'));
        toggleWidget(node, findWidgetByName(node, 'tile_height'));
    } else {
        toggleWidget(node, findWidgetByName(node, 'tile_width'), true);
        toggleWidget(node, findWidgetByName(node, 'tile_height'), true);
    }
}

// LoRA Stacker ED Handlers
function handleLoRAStackerEDInputMode(node, widget) {
    handleInputModeWidgetsVisibility(node, widget.value);
    handleVisibility(node, findWidgetByName(node, "lora_count"), "LoRA Stacker 💬ED");
    updateNodeHeight(node);
    node.setDirtyCanvas(true, true);
}

function handleLoRAStackerEDLoraCount(node, widget) {
    handleVisibility(node, widget, "LoRA Stacker 💬ED");
    updateNodeHeight(node);
    node.setDirtyCanvas(true, true);
}

// Keep the optional multi-LoRA sweep rows aligned with the selected count.
function handleEDLoraSweepCount(node, widget) {
    const count = Math.max(0, Math.min(9, Number(widget.value) || 0));
    // The legacy single-target controls remain available to old workflows but
    // are hidden once Add Lora mode is active.
    const multiMode = count > 0;
    toggleWidget(node, findWidgetByName(node, "target_lora"), !multiMode);
    toggleWidget(node, findWidgetByName(node, "first_strength"), !multiMode);
    toggleWidget(node, findWidgetByName(node, "last_strength"), !multiMode);
    toggleWidget(node, widget, false);
    for (let i = 1; i <= 9; i++) {
        const name = findWidgetByName(node, `scan_lora_name_${i}`);
        const toggle = findWidgetByName(node, `scan_lora_${i}_toggle`);
        const first = findWidgetByName(node, `scan_lora_first_strength_${i}`);
        const last = findWidgetByName(node, `scan_lora_last_strength_${i}`);
        const visible = i <= count;
        forceWidgetVisibility(node, name, visible);
        forceWidgetVisibility(node, toggle, visible);
        forceWidgetVisibility(node, first, visible);
        forceWidgetVisibility(node, last, visible);
        if (!visible && name) name.value = "None";
    }
    updateNodeHeight(node);
    node.setDirtyCanvas(true, true);
}

function getConnectedLoraNames(node) {
    const linkId = node.inputs?.find(input => input.name === "lora_pipe")?.link;
    const link = linkId != null ? app.graph.links[linkId] : null;
    const origin = link ? node.graph.getNodeById(link.origin_id) : null;
    if (!origin) return null;
    const names = [];
    for (const widget of origin.widgets || []) {
        const value = widget.value;
        if (value && typeof value === "object" && value.lora && !names.includes(value.lora)) {
            names.push(value.lora);
        }
    }
    return names.length ? ["None", ...names] : null;
}

function restrictSweepLoraCombos(node) {
    const names = getConnectedLoraNames(node);
    if (!names) return;
    for (let i = 1; i <= 9; i++) {
        const widget = findWidgetByName(node, `scan_lora_name_${i}`);
        if (!widget) continue;
        widget.options = widget.options || {};
        widget.options.values = names;
        if (!names.includes(widget.value)) widget.value = "None";
    }
    const legacy = findWidgetByName(node, "target_lora");
    if (legacy) {
        legacy.options = legacy.options || {};
        legacy.options.values = names;
        if (!names.includes(legacy.value)) legacy.value = names[1] || "None";
    }
}

function isEDLoraSweepNode(node) {
    const values = [node?.comfyClass, node?.type, node?.title,
        node?.properties?.["Node name for S&R"]];
    return values.some(value => String(value || "").includes("LoRA Sweep"));
}

function initEDLoraSweepUI(node) {
    if (!isEDLoraSweepNode(node)) return;
    const legacyName = findWidgetByName(node, "target_lora")?.value;
    const legacyFirst = findWidgetByName(node, "first_strength")?.value ?? 0.5;
    const legacyLast = findWidgetByName(node, "last_strength")?.value ?? 1.0;
    // Remove legacy fixed rows from an already-loaded node instance. Dynamic
    // rows below are the only scan controls rendered after this migration.
    if (node.widgets) {
        node.widgets = node.widgets.filter(widget =>
            !/^scan_lora_name_\d+$/.test(widget.name || "") &&
            !/^scan_lora_\d+_toggle$/.test(widget.name || "") &&
            !/^scan_lora_(first|last)_strength_\d+$/.test(widget.name || "") &&
            widget.name !== "scan_lora_count");
    }
    const legacy = findWidgetByName(node, "target_lora");
    if (legacy && legacyName && !legacy.value) legacy.value = legacyName;
    // The standalone ED.LoRASweepAddButton extension owns the chooser-backed
    // button. Do not create a competing plain button here.
    node.setSize([node.size[0], node.computeSize()[1]]);
    restrictSweepLoraCombos(node);
    if (!node.__edSweepConnectionBound) {
        node.__edSweepConnectionBound = true;
        const oldConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function () {
            const result = oldConnectionsChange?.apply(this, arguments);
            restrictSweepLoraCombos(this);
            return result;
        };
    }
    node.setDirtyCanvas(true, true);
}

// ComfyUI 0.3+ renders `hidden` widgets independently of widget.type. This
// fallback is required when another extension has replaced computeSize/type.
function forceWidgetVisibility(node, widget, visible) {
    if (!widget) return;
    widget.hidden = !visible;
    toggleWidget(node, widget, visible);
    if (!visible) widget.computeSize = () => [0, -4];
}

function addEDLoraSweepRow(node) {
    const rows = node.widgets.filter(widget => /^scan_lora_name_\d+$/.test(widget.name || ""));
    const next = rows.length + 1;
    if (next > 9) return;
    const names = getConnectedLoraNames(node) || ["None"];
    node.addWidget("combo", `scan_lora_name_${next}`, names, "None");
    node.addWidget("toggle", `scan_lora_${next}_toggle`, true);
    node.addWidget("number", `scan_lora_first_strength_${next}`, 0.5, null, { min: -10, max: 10, step: 0.01 });
    node.addWidget("number", `scan_lora_last_strength_${next}`, 1.0, null, { min: -10, max: 10, step: 0.01 });
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
}

// Embedding Stacker ED Handlers
function handleEmbeddingStacker(node, widget) {
    const posORneg = widget.name.substr(0, 3);
    handleVisibility(node, widget, "Embedding Stacker 💬ED_" + posORneg);
    updateNodeHeight(node);
    node.setDirtyCanvas(true, true);
}

function applyWidgetLogic_Init(node) {
    if (!NODE_WIDGET_HANDLERS[node.comfyClass]) return;

    for (const w of node.widgets) {
        if (!NODE_WIDGET_HANDLERS[node.comfyClass][w.name]) continue;

        let widgetValue = w.value;
        widgetLogic(node, w);

        // Define getters and setters for widget values
        Object.defineProperty(w, 'value', {
            get() {
                return widgetValue;
            },
            set(newVal) {
                if (newVal !== widgetValue) {
                    widgetValue = newVal;
                    widgetLogic(node, w);
                }
            }
        });
    }
}

app.registerExtension({
    name: "ED.DynamicWidgets",

    async beforeConfigureGraph() {
        dynamicWidgets_initialized = false;
    },

    nodeCreated(node) {
        edAppearance_Init(node);
        edComboWidget_Init(node);
        getBooruTagRegionalScript_Init(node);
        applyWidgetLogic_Init(node);
        initEDLoraSweepUI(node);
    },

    async afterConfigureGraph() {
        const filteredNodes = app.graph._nodes.filter(node => ED_COMBO_NODES.hasOwnProperty(node.comfyClass));
        filteredNodes.forEach(node => {
            node.widgets.forEach(widget => {
                if (widget.constructor.name === "EdToggleComboWidget") {
                    widget.setInitToggle();
                }
            });
        });
        // Existing workflow nodes may be restored before extension nodeCreated hooks;
        // initialize the compact sweep UI after graph deserialization as well.
        app.graph._nodes.forEach(node => initEDLoraSweepUI(node));

        setTimeout(() => {
            dynamicWidgets_initialized = true;
        }, 1000);
    },
});

// Power Loader-style Add Lora button for ED multi-target sweeps.
app.registerExtension({
    name: "ED.LoRASweepAddButton",
    nodeCreated(node) {
        initEDLoraSweepUI(node);
        const oldConnectionsChange = node.onConnectionsChange;
        node.onConnectionsChange = function () {
            const result = oldConnectionsChange?.apply(this, arguments);
            restrictSweepLoraCombos(this);
            return result;
        };
        node.setDirtyCanvas(true, true);
    },
});

