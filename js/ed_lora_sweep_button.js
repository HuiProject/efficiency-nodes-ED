import { app } from "../../../scripts/app.js";

const isSweep = n => [n?.type,n?.comfyClass,n?.title,n?.properties?.["Node name for S&R"]].some(v => String(v||"").includes("LoRA Sweep"));
const find = (n, name) => (n.widgets||[]).find(w => w.name === name);

function namesFromPipe(node) {
    const input = (node.inputs||[]).find(i => i.name === "lora_pipe");
    const link = input?.link != null ? app.graph.links[input.link] : null;
    const origin = link ? app.graph.getNodeById(link.origin_id) : null;
    if (!origin) return ["None"];
    const names = [];
    for (const w of origin.widgets||[]) {
        const v = w.value;
        if (v && typeof v === "object" && v.lora && !names.includes(v.lora)) names.push(v.lora);
    }
    return ["None", ...names];
}

function addRow(node, name) {
    if (!name || name === "None") return;
    const rows = (node.widgets||[]).filter(w => /^scan_lora_name_\d+$/.test(w.name||""));
    const index = rows.length + 1;
    if (index > 9) return;
    const names = namesFromPipe(node);
    node.addWidget("combo", `scan_lora_name_${index}`, names, name);
    node.addWidget("toggle", `scan_lora_${index}_toggle`, true);
    node.addWidget("number", `scan_lora_first_strength_${index}`, 0.5, null, {min:-10,max:10,step:0.01});
    node.addWidget("number", `scan_lora_last_strength_${index}`, 1.0, null, {min:-10,max:10,step:0.01});
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
    console.debug("[ED-UI] LoRA Sweep row added", {node:node.id,index,name});
}

function install(node) {
    if (!isSweep(node) || find(node,"ed_add_lora_sweep")) return;
    let chooser;
    chooser = node.addWidget("combo", "➕ Add Lora", namesFromPipe(node), "None", value => {
        console.debug("[ED-UI] LoRA Sweep chooser changed", {node:node.id,value});
        addRow(node, value);
        chooser.value = "None";
        node.setDirtyCanvas(true, true);
    });
    chooser.name = "ed_add_lora_sweep";
    chooser.serialize = false;
    chooser.options = chooser.options || {};
    chooser.options.serialize = false;
    node.__edSweepChooser = chooser;
}

function refresh(node) {
    const chooser = node.__edSweepChooser || find(node,"ed_add_lora_sweep");
    if (!chooser) return;
    const names = namesFromPipe(node);
    chooser.options ||= {};
    chooser.options.values = names;
    if (!names.includes(chooser.value)) chooser.value = "None";
}

function ensure(node) {
    if (!isSweep(node)) return;
    install(node); refresh(node);
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
}

app.registerExtension({name:"ED.LoRASweepNativeChooser", nodeCreated:ensure, async afterConfigureGraph(){for(const n of app.graph?._nodes||[]) ensure(n);}});
setInterval(() => { for (const n of app.graph?._nodes||[]) if (isSweep(n)) refresh(n); }, 1000);
