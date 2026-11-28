/* MythoGraph — frontend */
"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) n.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) n.append(k.nodeType ? k : String(k));
  return n;
};
const api = async (path, opts) => {
  const r = await fetch(path, opts);
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
};

const CATEGORY = {
  primordial: ["#5d4037", "Primordiale"], titan: ["#8d6e63", "Titano"], olympian: ["#c9a227", "Olimpico"],
  deity: ["#e0a84f", "Divinità"], minor: ["#9ccc65", "Divinità minore / ninfa"],
  demigod: ["#e65100", "Semidio (dedotto)"], hero: ["#d84315", "Eroe (dedotto)"], human: ["#42a5f5", "Umano"],
  monster: ["#6d4c41", "Mostro / ciclope"], creature: ["#a1887f", "Creatura"],
  event: ["#7e57c2", "Evento"], place: ["#26a69a", "Luogo reale"], mythplace: ["#80cbc4", "Luogo mitico"],
  other: ["#9e9e9e", "Altro"],
};
const SOURCE_COLORS = { hesiod: "#b8691c", homer: "#2b6c94", apollodorus: "#5c7a2e", pausanias: "#7b4a91",
  diodorus: "#a33b5c", herodotus: "#3d7f7a", hyginus: "#8a6d1f", apollonius: "#4b5aa8", wikidata: "#6b6b6b" };
const LEVEL_TEXT = { asserted: "asserita", shared: "condivisa", rules: "regola", owlrl: "OWL RL" };
const LEVEL_HELP = {
  asserted: "Affermata esplicitamente dalla fonte",
  shared: "Informazione condivisa da tutte le fonti",
  rules: "Dedotta da una regola SPARQL CONSTRUCT (ontology/rules)",
  owlrl: "Dedotta dalla chiusura OWL 2 RL (owlrl)",
};

const state = { sources: [], current: null, cy: null, source: "wikidata", view: "hood", depth: 1, data: null };

/* ------------------------------------------------------------------ helpers */
const sourceLabel = (name) => (state.sources.find((s) => s.name === name) || {}).label || name;
const srcBadge = (name) => el("span", { class: `src-badge src-${name}` }, name === "shared" ? "comune" : sourceLabel(name));
const lvlBadge = (lvl) => el("span", { class: `lvl lvl-${lvl}`, title: LEVEL_HELP[lvl] || "" }, LEVEL_TEXT[lvl] || lvl);

function renderNode(n) {
  if (!n) return el("span", { class: "muted" }, "—");
  if (n.literal !== undefined) return el("span", {}, n.literal);
  if (n.bnode) return el("span", { class: "muted" }, n.label);
  if (n.internal) return el("a", { class: "link", onclick: () => focusEntity(n.id) }, n.label);
  return el("span", { title: n.iri }, n.label);
}

function table(columns, rows) {
  if (!rows.length) return el("p", { class: "muted" }, "Nessun risultato.");
  return el("div", { class: "table-wrap" },
    el("table", { class: "res" },
      el("thead", {}, el("tr", {}, columns.map((c) => el("th", {}, c)))),
      el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, cell(c))))))));
}
function cell(c) {
  if (c && c.iri && c.iri.includes("/graph/")) {
    const name = c.iri.split("/graph/")[1];
    return SOURCE_COLORS[name] ? srcBadge(name) : el("code", {}, "g:" + name);
  }
  return renderNode(c);
}

/* ------------------------------------------------------------------- tabs */
function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-body").forEach((t) => (t.hidden = t.id !== `tab-${name}`));
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

/* ------------------------------------------------------------------ graph */
function initCy() {
  state.cy = cytoscape({
    container: $("#cy"),
    wheelSensitivity: 0.25,
    minZoom: 0.15, maxZoom: 3,
    style: [
      { selector: "node", style: {
        "background-color": "data(color)", label: "data(label)", "font-size": 11, color: "#2b2620",
        "text-valign": "bottom", "text-margin-y": 3, width: 22, height: 22,
        "text-outline-color": "#f6f1e7", "text-outline-width": 2, "border-width": 0 } },
      { selector: "node[?inferredCategory]", style: { "border-width": 3, "border-color": "#2b2620", "border-style": "dashed" } },
      { selector: "node[category = 'event']", style: { shape: "diamond" } },
      { selector: "node[category = 'place'], node[category = 'mythplace']", style: { shape: "round-rectangle" } },
      { selector: "edge", style: {
        width: 1.6, "line-color": "data(color)", "target-arrow-color": "data(color)",
        "target-arrow-shape": "triangle", "arrow-scale": 0.8, "curve-style": "bezier", opacity: 0.85 } },
      { selector: "edge[level != 'asserted']", style: { "line-style": "dashed", opacity: 0.6 } },
      { selector: "edge[kind = 'spouse']", style: { "target-arrow-shape": "none", "line-style": "dotted", width: 2 } },
      { selector: "edge[kind = 'killed']", style: { "target-arrow-shape": "tee", width: 2.2 } },
      { selector: "edge[?contested]", style: { "line-color": "#c62828", "target-arrow-color": "#c62828", width: 3.2, opacity: 1 } },
      { selector: ".faded", style: { opacity: 0.12, "text-opacity": 0.2 } },
      { selector: "node.focus", style: { width: 34, height: 34, "border-width": 4, "border-color": "#8a3b12", "font-size": 14, "font-weight": 700 } },
      { selector: "edge.hl", style: { opacity: 1 } },
      { selector: "edge.hover", style: { opacity: 1, width: 4, label: "data(label)", "font-size": 11, "z-index": 99,
        "text-background-color": "#fffdf8", "text-background-opacity": 1, "text-background-padding": 3 } },
    ],
  });
  // L'etichetta di un arco compare solo passandoci sopra col mouse.
  state.cy.on("mouseover", "edge", (e) => e.target.addClass("hover"));
  state.cy.on("mouseout", "edge", (e) => e.target.removeClass("hover"));
  state.cy.on("tap", "node", (e) => focusEntity(e.target.id(), state.view !== "all"));
  state.cy.on("tap", (e) => { if (e.target === state.cy && state.view === "all") clearFocus(); });
}

/* Scarica il grafo della fonte scelta; il disegno (render) avviene lato client. */
async function loadGraph() {
  const p = new URLSearchParams({
    source: state.source, inferred: $("#inferred").checked, events: $("#events").checked, places: $("#places").checked,
  });
  $("#graph-status").textContent = "Caricamento…";
  state.data = await api(`/api/graph?${p}`);
  render();
}

const FAMILY = new Set(["hasFather", "hasMother", "hasParent"]);
const push = (map, k, v) => { if (!map.has(k)) map.set(k, []); map.get(k).push(v); };

/* Sottografo: vicini fino a `depth` passi dal nodo `id` (archi in entrambe le direzioni). */
function neighbourhood(data, id, depth) {
  const adj = new Map();
  for (const e of data.edges) { push(adj, e.source, e.target); push(adj, e.target, e.source); }
  const dist = new Map([[id, 0]]);
  let frontier = [id];
  for (let d = 1; d <= depth; d++) {
    const next = [];
    for (const n of frontier) for (const m of adj.get(n) || []) if (!dist.has(m)) { dist.set(m, d); next.push(m); }
    frontier = next;
  }
  return dist;
}

/* Albero genealogico: antenati (livelli negativi, in alto) e discendenti (positivi, in basso). */
function genealogy(data, id, maxDown = 2) {
  const parents = new Map(), children = new Map();
  for (const e of data.edges) {
    if (!FAMILY.has(e.prop)) continue;               // arco figlio → genitore
    push(parents, e.source, e.target);
    push(children, e.target, e.source);
  }
  const level = new Map([[id, 0]]);
  let frontier = [id];
  for (let d = 1; frontier.length; d++) {            // risali tutti gli antenati
    const next = [];
    for (const n of frontier) for (const p of parents.get(n) || []) if (!level.has(p)) { level.set(p, -d); next.push(p); }
    frontier = next;
  }
  frontier = [id];
  for (let d = 1; d <= maxDown && frontier.length; d++) {   // scendi di qualche generazione
    const next = [];
    for (const n of frontier) for (const c of children.get(n) || []) if (!level.has(c)) { level.set(c, d); next.push(c); }
    frontier = next;
  }
  return level;
}

function render() {
  const data = state.data;
  if (!data) return;
  const cy = state.cy;
  const view = state.view;
  $("#map").hidden = view !== "map";
  $("#cy").style.visibility = view === "map" ? "hidden" : "visible";
  $("#legend").hidden = view === "map";
  $("#fit").hidden = view === "map";
  if (view === "map") { renderMap(); return; }
  const colorEdge = (e) => (e.kind === "killed" ? "#5d4037" : state.source === "all" ? SOURCE_COLORS[e.graph] : "#8d8478");
  const byId = new Map(data.nodes.map((n) => [n.id, n]));
  if (view !== "all" && (!state.current || !byId.has(state.current))) state.current = byId.has("Zeus") ? "Zeus" : data.nodes[0]?.id;

  let keep, levels;
  if (view === "hood") keep = neighbourhood(data, state.current, state.depth);
  else if (view === "tree") { levels = genealogy(data, state.current); keep = levels; }
  else keep = new Map(data.nodes.map((n) => [n.id, 0]));

  const edges = data.edges.filter((e) => keep.has(e.source) && keep.has(e.target)
    && (view !== "tree" || FAMILY.has(e.prop) || e.kind === "spouse"));
  const nodes = [...keep.keys()].filter((k) => byId.has(k)).map((k) => byId.get(k));

  cy.elements().remove();
  cy.add([
    ...nodes.map((n) => ({ data: { ...n, color: (CATEGORY[n.category] || CATEGORY.other)[0], dist: keep.get(n.id) } })),
    ...edges.map((e) => ({ data: { ...e, color: colorEdge(e) } })),
  ]);

  if (view === "hood") {
    cy.layout({ name: "concentric", concentric: (n) => 10 - n.data("dist"), levelWidth: () => 1,
                minNodeSpacing: 30, animate: false }).run();
  } else if (view === "tree") {
    // posizioni calcolate a mano: una riga per generazione
    const rows = new Map();
    for (const [id, lv] of levels) push(rows, lv, id);
    const positions = {};
    for (const [lv, ids] of rows) {
      ids.sort((a, b) => (byId.get(a)?.label || a).localeCompare(byId.get(b)?.label || b));
      ids.forEach((id, i) => { positions[id] = { x: (i - (ids.length - 1) / 2) * 115, y: lv * 120 }; });
    }
    cy.layout({ name: "preset", positions: (n) => positions[n.id()], animate: false }).run();
  } else {
    cy.layout({ name: "cose", animate: false, nodeRepulsion: 9000, idealEdgeLength: 70, gravity: 0.35,
                numIter: 1500, randomize: true, componentSpacing: 60 }).run();
  }
  cy.fit(undefined, 40);

  const inf = edges.filter((e) => e.level !== "asserted").length;
  const cls = nodes.filter((n) => n.inferredCategory).length;
  const who = byId.get(state.current)?.label;
  const prefix = view === "hood" ? `Vicinato di ${who} · ` : view === "tree" ? `Albero di ${who} · ` : "";
  $("#graph-status").textContent = `${prefix}${nodes.length} nodi · ${edges.length} archi`
    + (inf ? ` (${inf} dedotti)` : "") + (cls ? ` · ${cls} classificazioni dedotte` : "");
  renderLegend();
  if (state.current) highlight(state.current);
}

/* Mappa dei luoghi reali: coordinate prese da Wikidata con la query federata. */
async function renderMap() {
  if (!state.map) {
    state.map = L.map("map", { zoomControl: true }).setView([38.5, 20], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12, attribution: "&copy; OpenStreetMap contributors · coordinate: Wikidata",
    }).addTo(state.map);
    state.mapLayer = L.layerGroup().addTo(state.map);
  }
  const places = await api(`/api/places?source=${state.source}`);
  state.map.invalidateSize();                    // il contenitore era nascosto: ricalcola le dimensioni
  state.mapLayer.clearLayers();
  for (const p of places) {
    const n = p.events.length;
    const srcs = [...new Set(p.events.map((e) => e.source))];
    const color = n === 0 ? "#9e9e9e" : srcs.length > 1 ? "#8a3b12" : SOURCE_COLORS[srcs[0]];
    const marker = L.circleMarker([p.lat, p.long], {
      radius: n ? 7 + 3 * Math.min(n, 4) : 5, color: "#fff", weight: 1.5, fillColor: color, fillOpacity: 0.9,
    }).addTo(state.mapLayer);
    const box = el("div", {},
      el("h4", {}, p.label),
      n ? el("ul", {}, p.events.map((e) => el("li", {},
            srcBadge(e.source), " ",
            el("a", { class: "link", onclick: () => focusEntity(e.id) }, e.label),
            e.approx ? el("span", { class: "muted" }, ` (${e.place})`) : null)))
        : el("div", { class: "muted" }, "Nessun evento ambientato qui"),
      el("div", { style: "margin-top:6px" }, el("a", { class: "link", onclick: () => focusEntity(p.id) }, "Scheda del luogo")));
    marker.bindPopup(box);
    marker.bindTooltip(p.label + (n ? ` · ${n} eventi` : ""));
  }
  const pts = places.filter((p) => p.events.length).map((p) => [p.lat, p.long]);
  if (pts.length && !state.mapFitted) { state.map.fitBounds(pts, { padding: [30, 30] }); state.mapFitted = true; }
  const withEvents = places.filter((p) => p.events.length).length;
  $("#graph-status").textContent = `Mappa · ${places.length} luoghi reali · ${withEvents} con eventi · coordinate da Wikidata`;
}

function renderLegend() {
  const used = new Set(state.cy.nodes().map((n) => n.data("category")));
  const items = Object.entries(CATEGORY).filter(([k]) => used.has(k))
    .map(([, [c, l]]) => el("div", { class: "item" }, el("span", { class: "sw", style: `background:${c}` }), l));
  const lines = state.source === "all"
    ? state.sources.filter((s) => SOURCE_COLORS[s.name]).map((s) =>
        el("div", { class: "item" }, el("span", { class: "ln", style: `border-color:${SOURCE_COLORS[s.name]}` }), s.label))
    : [];
  $("#legend").replaceChildren(...items, ...lines,
    el("div", { class: "item" }, el("span", { class: "ln dashed", style: "border-color:#555" }), "dedotto"),
    el("div", { class: "item" }, el("span", { class: "ln", style: "border-color:#c62828" }), "contestato"));
}

function highlight(id) {
  const cy = state.cy;
  cy.elements().removeClass("faded focus hl");
  const n = cy.getElementById(id);
  if (!n.nonempty()) return;
  if (state.view === "all") cy.elements().not(n.closedNeighborhood()).addClass("faded");
  n.addClass("focus");
  n.connectedEdges().addClass("hl");
}
function clearFocus() { state.cy.elements().removeClass("faded focus hl"); }

/* Seleziona un personaggio: apre la scheda e, nelle viste locali, ricentra il grafo su di lui. */
async function focusEntity(id, redraw = true) {
  state.current = id;
  if (state.view === "map") { /* la mappa resta com'è: si apre solo la scheda */ }
  else if (state.view !== "all" && redraw) render();
  else {
    highlight(id);
    const n = state.cy.getElementById(id);
    if (n.nonempty()) state.cy.animate({ center: { eles: n }, zoom: Math.max(state.cy.zoom(), 1.1) }, { duration: 300 });
  }
  showTab("entity");
  await renderEntity(id);
}

/* ------------------------------------------------------------------ scheda */
async function renderEntity(id) {
  const box = $("#tab-entity");
  box.replaceChildren(el("p", { class: "muted" }, "Caricamento…"));
  let e;
  try { e = await api(`/api/entity/${encodeURIComponent(id)}?source=${state.source}`); }
  catch (err) { box.replaceChildren(el("p", { class: "status-bad" }, err.message)); return; }

  const alt = ["en", "grc", "la"].filter((l) => e.labels[l] && e.labels[l] !== e.label).map((l) => e.labels[l]);
  const head = el("div", { class: "card-head" },
    el("h2", {}, e.label), alt.length ? el("div", { class: "alt" }, alt.join(" · ")) : null,
    el("div", { class: "iri" }, e.iri));

  const types = el("div", { class: "section" }, el("h3", {}, "Classi"),
    el("div", { class: "chips" }, e.types.map((t) =>
      el("span", { class: "chip", title: t.levelLabel }, t.class.label, " ", lvlBadge(t.level)))));

  const sections = [head, types];

  const ext = e.external || {};
  if (ext.wikidata || ext.dbpedia || ext.wikipedia || e.romanNames.length || e.greekName) {
    sections.push(el("div", { class: "section" }, el("h3", {}, "Collegamenti (linked data)"),
      el("div", { class: "ext" },
        ext.wikidata ? el("a", { href: ext.wikidata, target: "_blank", rel: "noopener" }, "Wikidata " + ext.wikidata.split("/").pop()) : null,
        ext.dbpedia ? el("a", { href: ext.dbpedia, target: "_blank", rel: "noopener" }, "DBpedia") : null,
        ext.wikipedia ? el("a", { href: ext.wikipedia, target: "_blank", rel: "noopener" }, "Wikipedia") : null),
      ext.lat != null ? el("div", { class: "muted", style: "font-size:12px" }, `Coordinate (Wikidata): ${ext.lat}, ${ext.long}`) : null,
      e.romanNames.length ? el("div", {}, "Nome romano: ", ...e.romanNames.map((r) => renderNode(r)),
        el("span", { class: "muted" }, " (identificati con owl:sameAs solo nel grafo di Ovidio)")) : null,
      e.greekName ? el("div", {}, "Corrispettivo greco: ", renderNode(e.greekName),
        el("span", { class: "muted" }, " (owl:sameAs nel grafo di Ovidio)")) : null));
  }

  if (e.conflicts.length) {
    sections.push(el("div", { class: "section" }, el("h3", {}, "Versioni in disaccordo"),
      e.conflicts.map((c) => el("div", { class: "box alert" },
        el("strong", {}, c.property.label), ": ",
        srcBadge(c.source1), " ", renderNode(c.value1), "  ≠  ", srcBadge(c.source2), " ", renderNode(c.value2)))));
  }
  if (e.comments.length) {
    sections.push(el("div", { class: "section" }, e.comments.map((c) => el("p", { class: "quote" }, c))));
  }

  // fatti raggruppati per fonte
  const bySource = {};
  for (const f of e.facts) (bySource[f.source] ||= []).push(f);
  const order = ["shared", ...state.sources.map((s) => s.name)];
  for (const src of order) {
    const facts = bySource[src];
    if (!facts) continue;
    facts.sort((a, b) => (a.level === "asserted" || a.level === "shared" ? 0 : 1) - (b.level === "asserted" || b.level === "shared" ? 0 : 1)
      || a.prop.label.localeCompare(b.prop.label));
    sections.push(el("div", { class: "section" },
      el("h3", {}, srcBadge(src), src === "shared" ? " Informazioni comuni" : " Secondo questa fonte"),
      el("table", { class: "facts" }, el("tbody", {}, facts.map((f) =>
        el("tr", {},
          el("td", { class: "p" }, f.dir === "in" ? "← " : "", f.prop.label),
          el("td", {}, renderNode(f.value)),
          el("td", {}, lvlBadge(f.level))))))));
  }

  if (e.attestations.length) {
    sections.push(el("div", { class: "section" }, el("h3", {}, "Attestazioni (reificazione)"),
      e.attestations.map((a) => el("div", { class: "box" },
        srcBadge(a.source), " ", el("strong", {}, a.passage || ""), el("br"),
        renderNode(a.subject), " ", el("em", {}, a.predicate.label), " ", renderNode(a.object),
        a.note ? el("div", { class: "quote" }, a.note) : null))));
  }
  box.replaceChildren(...sections);
}

/* ----------------------------------------------------------------- ricerca */
let searchTimer;
$("#search").addEventListener("input", (ev) => {
  clearTimeout(searchTimer);
  const q = ev.target.value.trim();
  const ul = $("#search-results");
  if (!q) { ul.hidden = true; return; }
  searchTimer = setTimeout(async () => {
    const hits = await api(`/api/search?q=${encodeURIComponent(q)}`);
    ul.replaceChildren(...hits.map((h) => el("li", { onclick: () => { ul.hidden = true; $("#search").value = h.label; focusEntity(h.id); } },
      el("span", { class: "sw", style: `width:10px;height:10px;border-radius:50%;display:inline-block;background:${(CATEGORY[h.category] || CATEGORY.other)[0]}` }), h.label)));
    ul.hidden = !hits.length;
  }, 150);
});
$("#search").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") { const first = $("#search-results li"); if (first) first.click(); }
  if (ev.key === "Escape") $("#search-results").hidden = true;
});
document.addEventListener("click", (ev) => { if (!ev.target.closest(".search")) $("#search-results").hidden = true; });

/* --------------------------------------------------------------- conflitti */
async function renderConflicts() {
  const list = await api("/api/conflicts");
  const box = $("#tab-conflicts");
  box.replaceChildren(
    el("p", { class: "hint" }, "Affermazioni su cui le fonti non sono d'accordo (CQ2). Ogni fonte è un named graph separato, quindi le versioni convivono senza contraddizioni. Fondendole ingenuamente l'ontologia diventerebbe inconsistente (vedi scheda Fonti)."),
    ...list.map((c) => el("div", { class: "box alert" },
      el("a", { class: "link", onclick: () => focusEntity(c.character.id) }, c.character.label), " — ",
      el("strong", {}, c.property.label), el("br"),
      srcBadge(c.source1), " ", renderNode(c.value1), "   vs   ", srcBadge(c.source2), " ", renderNode(c.value2),
      el("div", { class: "muted", style: "font-size:12px" }, c.kind))));
}

/* -------------------------------------------------------------------- CQ */
async function renderCQs() {
  const cqs = await api("/api/cq");
  const box = $("#tab-cq");
  box.replaceChildren(el("p", { class: "hint" }, "Le competency question guidano la progettazione dell'ontologia: ognuna è una query SPARQL in queries/ ed è verificata da un test."));
  for (const cq of cqs) {
    const out = el("div");
    const target = cq.target ? el("input", { type: "text", value: cq.target.id, size: 14, title: "Identificativo della risorsa (es. Zeus, Achilles)" }) : null;
    const run = async () => {
      out.replaceChildren(el("p", { class: "muted" }, "Esecuzione…"));
      try {
        const q = target && target.value.trim() ? `?target=${encodeURIComponent(target.value.trim())}` : "";
        const r = await api(`/api/cq/${cq.number}${q}`);
        out.replaceChildren(el("p", { class: "muted" }, `${r.rows.length} risultati`), table(r.columns, r.rows));
      } catch (err) { out.replaceChildren(el("p", { class: "status-bad" }, err.message)); }
    };
    box.append(el("div", { class: "cq" },
      el("h3", {}, el("span", { class: "num" }, `CQ${cq.number}`), cq.title),
      el("div", { class: "row" }, target ? el("label", { class: "muted" }, "risorsa: ", target) : null,
        el("button", { class: "primary", onclick: run }, "Esegui"),
        el("button", { class: "secondary", onclick: () => { $("#sparql-text").value = cq.query; showTab("sparql"); } }, "Apri in SPARQL")),
      el("details", {}, el("summary", {}, "Spiegazione e query"), el("p", {}, cq.comment), el("pre", {}, cq.query)),
      out));
  }
}

/* ----------------------------------------------------------------- SPARQL */
$("#sparql-text").value = `PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX myth: <https://example.org/mythograph/ontology#>
PREFIX res:  <https://example.org/mythograph/resource/>
PREFIX g:    <https://example.org/mythograph/graph/>

# Chi sono i figli di Zeus, e secondo quale fonte?
SELECT ?fonte ?figlio WHERE {
  GRAPH ?fonte { ?figlio myth:hasFather res:Zeus }
  GRAPH g:meta { ?fonte a myth:SourceGraph }
}
ORDER BY ?fonte ?figlio`;
$("#sparql-run").addEventListener("click", async () => {
  const msg = $("#sparql-msg"), out = $("#sparql-out");
  msg.textContent = "Esecuzione…"; out.replaceChildren();
  const t0 = performance.now();
  try {
    const r = await api("/api/sparql", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: $("#sparql-text").value }) });
    msg.textContent = `${r.type} · ${Math.round(performance.now() - t0)} ms`;
    if (r.type === "ASK") out.replaceChildren(el("p", { class: r.boolean ? "status-ok" : "status-bad" }, r.boolean ? "true" : "false"));
    else out.replaceChildren(el("p", { class: "muted" }, `${r.rows.length} righe`), table(r.columns, r.rows));
  } catch (err) { msg.textContent = ""; out.replaceChildren(el("p", { class: "status-bad" }, err.message)); }
});

/* ------------------------------------------------------------------ fonti */
function renderSources() {
  const yes = (v) => v === null || v === undefined ? el("span", { class: "muted" }, "n/d")
    : el("span", { class: v ? "status-ok" : "status-bad" }, v ? "consistente" : "INCONSISTENTE");
  $("#tab-sources").replaceChildren(
    el("p", { class: "hint" }, "Ogni fonte viene ragionata separatamente (TBox + entità comuni + fonte). La fusione ingenua mette tutte le fonti nello stesso grafo: le proprietà funzionali hasFather/hasMother fanno dedurre owl:sameAs tra personaggi diversi, in contrasto con owl:AllDifferent."),
    ...state.sources.map((s) => el("div", { class: "box" + (s.consistentOWLRL === false ? " alert" : "") },
      srcBadge(s.name), " ", el("strong", {}, s.works.join(", ") || s.label), el("br"),
      s.asserted != null ? el("div", { class: "muted" }, `${s.asserted} triple asserite · dedotte: regole ${s.inferred.rules}, OWL RL ${s.inferred.owlrl}`) : null,
      el("div", {}, "OWL RL: ", yes(s.consistentOWLRL)),
      s.errors.length ? el("details", {}, el("summary", {}, `${s.errors.length} violazioni`),
        el("ul", {}, s.errors.map((er) => el("li", { style: "font-size:12px" }, er.replaceAll("https://example.org/mythograph/resource/", "res:"))))) : null)));
}

/* ------------------------------------------------------------------- avvio */
async function main() {
  initCy();
  state.sources = await api("/api/sources");
  const sel = $("#source");
  sel.replaceChildren(el("option", { value: "all" }, "Tutte le fonti antiche"),
    ...state.sources.filter((s) => s.name !== "merged-naive").map((s) =>
      el("option", { value: s.name }, s.works.length ? `${s.label} (${s.works.join(", ")})` : s.label)));
  sel.value = state.source;
  sel.addEventListener("change", () => { state.source = sel.value; loadGraph(); if (state.current) renderEntity(state.current); });
  ["#inferred", "#events", "#places"].forEach((id) => $(id).addEventListener("change", loadGraph));
  $("#view").addEventListener("change", (ev) => { state.view = ev.target.value; $("#depth-field").hidden = state.view !== "hood"; render(); });
  $("#inferred").closest("label").title = "Mostra anche le relazioni e le classi dedotte dal ragionamento";
  $("#depth").addEventListener("change", (ev) => { state.depth = Number(ev.target.value); render(); });
  $("#fit").addEventListener("click", () => state.cy.fit(undefined, 30));
  renderSources();
  await loadGraph();
  if (state.current) renderEntity(state.current);
  renderConflicts();
  renderCQs();
}
main().catch((err) => { $("#graph-status").textContent = "Errore: " + err.message; console.error(err); });
