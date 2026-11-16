"use strict";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
let current = null; // last result
let outView = "overview";

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) n.append(kid);
  return n;
}
const flat = (v) => (v && typeof v === "object" ? v.raw ?? JSON.stringify(v) : v == null ? "" : String(v));
const setStatus = (t) => ($("#status").textContent = t);

/* ---------- engine pill ---------- */
fetch("/api/health").then((r) => r.json()).then((h) => {
  const p = $("#engine");
  p.textContent = h.llm_enabled ? `Claude + rules (${h.model})` : "Offline rules engine";
  p.classList.toggle("ok", true);
}).catch(() => ($("#engine").textContent = "Server not reachable"));

/* ---------- tabs ---------- */
$$("[data-view]").forEach((b) => b.addEventListener("click", () => {
  $$("[data-view]").forEach((x) => x.classList.toggle("on", x === b));
  const marked = b.dataset.view === "marked";
  $("#text").hidden = marked;
  $("#marked").hidden = !marked;
  if (marked) renderMarked();
}));
$$("[data-out]").forEach((b) => b.addEventListener("click", () => {
  outView = b.dataset.out;
  $$("[data-out]").forEach((x) => x.classList.toggle("on", x === b));
  renderOut();
}));

/* ---------- highlighting ---------- */
function collectSpans(result) {
  const out = [];
  for (const [kind, items] of Object.entries(result.entities || {}))
    for (const it of items) { const v = flat(it).trim(); if (v.length > 2) out.push([v, kind]); }
  return out;
}
function renderMarked() {
  const box = $("#marked"); box.replaceChildren();
  const text = $("#text").value;
  const spans = current ? collectSpans(current) : [];
  if (!spans.length) { box.textContent = text || "Run an extraction to see entities highlighted here."; return; }
  const kindOf = new Map(spans.map(([v, k]) => [v, k]));
  const rx = new RegExp([...kindOf.keys()].sort((a, b) => b.length - a.length).map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "g");
  let last = 0, m;
  while ((m = rx.exec(text))) {
    if (m.index > last) box.append(text.slice(last, m.index));
    const kind = kindOf.get(m[0]) || "other";
    box.append(el("mark", { class: "k-" + kind, title: kind, text: m[0] }));
    last = m.index + m[0].length;
  }
  box.append(text.slice(last));
}
function renderLegend() {
  const lg = $("#legend"); lg.replaceChildren();
  if (!current) return;
  for (const [kind, items] of Object.entries(current.entities || {}))
    lg.append(el("span", { class: "chip k-" + kind, text: `${kind.replace("_", " ")} ${items.length}` }));
}

/* ---------- output rendering ---------- */
function kvTable(obj) {
  const t = el("table", { class: "kv" });
  for (const [k, v] of Object.entries(obj)) t.append(el("tr", {}, el("th", { text: k }), el("td", { text: flat(v) || "—" })));
  return t;
}
function dataTable(headers, rows) {
  const t = el("table", { class: "kv data" });
  t.append(el("thead", {}, el("tr", {}, headers.map((h) => el("th", { text: h })))));
  t.append(el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => el("td", { text: flat(c) }))))));
  return el("div", { class: "tablewrap" }, t);
}
function renderOut() {
  const box = $("#out"); box.replaceChildren();
  const r = current;
  if (!r) { box.append(el("p", { class: "muted", text: "Results appear here. Try a sample, then choose Extract structure." })); return; }
  (r.meta?.warnings || []).forEach((w) => box.append(el("div", { class: "warn", text: w })));

  if (outView === "json") { box.append(el("pre", { class: "json", text: JSON.stringify(r, null, 2) })); return; }

  if (outView === "entities") {
    const ents = Object.entries(r.entities || {});
    if (!ents.length) box.append(el("p", { class: "muted", text: "No entities found in this text." }));
    ents.forEach(([k, items]) => {
      box.append(el("h3", { text: `${k.replace("_", " ")} (${items.length})` }));
      box.append(el("ul", { class: "plain" }, items.map((i) => el("li", { text: typeof i === "object" ? Object.values(i).filter((x) => x !== null && x !== "").join("  ·  ") : i }))));
    });
    return;
  }

  if (outView === "tables") {
    const tables = r.tables || [];
    if (!tables.length && !(r.line_items || []).length) box.append(el("p", { class: "muted", text: "No tables or line items detected." }));
    tables.forEach((t, i) => { box.append(el("h3", { text: `Table ${i + 1}` })); box.append(dataTable(t.headers, t.rows)); });
    if ((r.line_items || []).length) {
      box.append(el("h3", { text: "Line items" }));
      box.append(dataTable(["Description", "Qty", "Unit price", "Line total"], r.line_items.map((i) => [i.description, i.quantity, i.unit_price, i.line_total])));
      if (r.computed_total != null) box.append(el("p", { class: "muted", text: `Computed total of line items: ${r.computed_total}` }));
    }
    return;
  }

  // overview
  const pct = r.confidence != null ? ` · confidence ${Math.round(r.confidence * 100)}%` : "";
  box.append(el("p", {}, el("span", { class: "badge", text: String(r.document_type || "document").replace(/_/g, " ") }), el("span", { class: "muted", text: pct })));
  if (r.summary) box.append(el("p", { text: r.summary }));
  if (r.keywords?.length) box.append(el("p", {}, r.keywords.map((k) => el("span", { class: "chip", text: k }))));
  if (r.custom_fields && Object.keys(r.custom_fields).length) { box.append(el("h3", { text: "Requested fields" })); box.append(kvTable(r.custom_fields)); }
  if (r.fields && Object.keys(r.fields).length) { box.append(el("h3", { text: "Detected fields" })); box.append(kvTable(r.fields)); }
  if (r.action_items?.length) { box.append(el("h3", { text: "Action items" })); box.append(el("ul", { class: "plain" }, r.action_items.map((a) => el("li", { text: a })))); }
  if (r.stats) box.append(el("p", { class: "muted", text: `${r.stats.words} words · ${r.stats.lines} lines · ${r.meta?.mode_used || ""} · ${r.meta?.elapsed_ms ?? ""} ms` }));
}

/* ---------- extraction ---------- */
function fieldList() { return $("#fields").value.split(/[,\n]/).map((s) => s.trim()).filter(Boolean); }

async function extract(file) {
  const go = $("#go"); go.disabled = true; setStatus("Extracting…");
  try {
    let res;
    if (file) {
      const fd = new FormData();
      fd.append("file", file); fd.append("fields", fieldList().join(",")); fd.append("mode", $("#mode").value);
      res = await fetch("/api/extract/file", { method: "POST", body: fd });
    } else {
      const text = $("#text").value;
      if (!text.trim()) { setStatus("Paste some text or upload a file first."); return; }
      res = await fetch("/api/extract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, fields: fieldList(), mode: $("#mode").value }) });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed");
    if (data.source_text) { $("#text").value = data.source_text; delete data.source_text; }
    current = data; outView = "overview";
    $$("[data-out]").forEach((x) => x.classList.toggle("on", x.dataset.out === "overview"));
    renderOut(); renderLegend(); if (!$("#marked").hidden) renderMarked();
    setStatus("Done."); loadHistory();
  } catch (e) { setStatus("Error: " + e.message); }
  finally { go.disabled = false; }
}
$("#go").addEventListener("click", () => extract());

$("#file").addEventListener("change", (e) => {
  const f = e.target.files[0]; if (!f) return;
  $("#fname").textContent = f.name; extract(f); e.target.value = "";
});
$("#sample").addEventListener("change", async (e) => {
  if (!e.target.value) return;
  const t = await (await fetch("/samples/" + e.target.value)).text();
  $("#text").value = t; current = null; renderOut(); renderLegend();
  if (e.target.value.includes("invoice")) $("#fields").value = "invoice number, total, due date, email";
  else if (e.target.value.includes("messy")) $("#fields").value = "priority, budget, phone";
  else $("#fields").value = "";
  e.target.value = ""; setStatus("Sample loaded. Choose Extract structure.");
});

/* ---------- export ---------- */
function download(name, content, type) {
  const a = el("a", { href: URL.createObjectURL(new Blob([content], { type })), download: name });
  document.body.append(a); a.click(); a.remove();
}
$$("[data-export]").forEach((b) => b.addEventListener("click", async () => {
  if (!current) return setStatus("Nothing to export yet.");
  const fmt = b.dataset.export;
  if (fmt === "json") return download("structuriq-result.json", JSON.stringify(current, null, 2), "application/json");
  const res = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ result: current, format: fmt }) });
  download("structuriq-result." + fmt, await res.text(), res.headers.get("content-type") || "text/plain");
}));
$("#copy").addEventListener("click", async () => {
  if (!current) return setStatus("Nothing to copy yet.");
  try { await navigator.clipboard.writeText(JSON.stringify(current, null, 2)); setStatus("JSON copied."); } catch { setStatus("Copy blocked by the browser."); }
});

/* ---------- history ---------- */
async function loadHistory() {
  const ul = $("#history");
  try {
    const items = await (await fetch("/api/history")).json();
    ul.replaceChildren();
    if (!items.length) { ul.append(el("li", { class: "muted", text: "No extractions yet." })); return; }
    items.forEach((i) => {
      const load = el("button", { class: "load", title: "Open this extraction", text: `#${i.id} · ${i.doc_type} · ${i.preview}` });
      load.addEventListener("click", async () => {
        const item = await (await fetch("/api/history/" + i.id)).json();
        $("#text").value = item.text; current = item.result; renderOut(); renderLegend();
        if (!$("#marked").hidden) renderMarked();
      });
      const del = el("button", { class: "del", "aria-label": "Delete extraction " + i.id, text: "×" });
      del.addEventListener("click", async () => { await fetch("/api/history/" + i.id, { method: "DELETE" }); loadHistory(); });
      ul.append(el("li", {}, load, del));
    });
  } catch { /* server offline */ }
}
loadHistory();
