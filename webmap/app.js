"use strict";

// Page-level settings (see index.html / live.html):
//   base:              basemap file stem (PNG + JSON extent sidecar)
//   dynamicGridLabels: draw USNG grid labels pinned to the viewport edges
//   data:              path to a feed snapshot -> static replay mode;
//                      null/absent -> poll the live bayou feed
//   labelStyle:        "chip" (default, white box beside dot) or
//                      "ondot" (white number centered on the dot)
//   goals:             [{node: 3, square: "025-270"}, ...] — mark a node's
//                      target 100 m square in that node's color
const { base: BASE, dynamicGridLabels, data: DATA_URL } = window.APP_CONFIG;
const LABEL_STYLE = window.APP_CONFIG.labelStyle || "chip";
const GOALS = window.APP_CONFIG.goals || [];

const FEED = "https://bayou.pvos.org/data/995ywq4zg2iq";
const POLL_LATEST_MS = 5000;        // live: per-node latest position
const RESCAN_MS = 120000;           // live: full-feed rescan for new nodes
const STALE_MS = 120000;            // fade nodes with no fix in this window
const TRAIL_MAX = 100;
const HISTORY_MAX = 20000;          // per-node fix cap (memory guard)

const PALETTE = ["#e53935", "#1e88e5", "#43a047", "#fb8c00", "#8e24aa",
                 "#00acc1", "#f06292", "#6d4c41", "#c0ca33", "#5c6bc0"];

const UTM19 = "+proj=utm +zone=19 +datum=WGS84 +units=m +no_defs";
const llToUtm = (lat, lon) => proj4("WGS84", UTM19, [lon, lat]);

let META, map;
let replayT = null;                 // static mode: current scrubber time (ms)
const nodes = new Map();            // node_id -> state

const statusEl = document.getElementById("status");
const nodesEl = document.getElementById("nodes");
const setStatus = (msg, err = false) => {
  statusEl.textContent = msg;
  statusEl.className = err ? "err" : "";
};
const nowMs = () => (replayT ?? Date.now());

// --- coordinate helpers -------------------------------------------------
const utmToMap = (x, y) => [
  (y - META.y0) / (META.y1 - META.y0) * META.height_px,
  (x - META.x0) / (META.x1 - META.x0) * META.width_px,
];
const mapToUtm = (latlng) => [
  META.x0 + latlng.lng / META.width_px * (META.x1 - META.x0),
  META.y0 + latlng.lat / META.height_px * (META.y1 - META.y0),
];
const onMap = (x, y) =>
  x >= META.x0 && x <= META.x1 && y >= META.y0 && y <= META.y1;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const pad3 = (n) => String(n).padStart(3, "0");
const gridLabel = (m) => pad3(Math.floor((m % 100000) / 100));
const usngSquare = (x, y) => `${gridLabel(x)}-${gridLabel(y)}`;
const usngFull = (x, y) =>
  `${META.utm_zone} ${META.square_100km} ` +
  `${String(Math.floor(x % 100000)).padStart(5, "0")} ` +
  `${String(Math.floor(y % 100000)).padStart(5, "0")}`;

const validFix = (p) =>
  typeof p.gps_lat === "number" && typeof p.gps_lon === "number" &&
  !(p.gps_lat === 0 && p.gps_lon === 0);

const agoText = (t) => {
  const s = Math.max(0, (nowMs() - t) / 1000);
  if (s < 90) return `${Math.round(s)} s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  return `${(s / 3600).toFixed(1)} h ago`;
};

// --- dynamic grid labels (pinned to the viewport at any zoom) ------------
function setupGridLabels() {
  const layer = L.layerGroup().addTo(map);
  const SHIFT = {   // keep chips just inside the viewport edge
    bottom: "translate(-50%,-130%)", top: "translate(-50%,30%)",
    left: "translate(6px,-50%)", right: "translate(calc(-100% - 6px),-50%)",
  };
  const chip = (pos, text, bold, edge) => L.marker(pos, {
    interactive: false, keyboard: false,
    icon: L.divIcon({ className: "", iconSize: null, html:
      `<div class="grid-chip ${bold ? "bold" : ""}"
            style="transform:${SHIFT[edge]}">${text}</div>` }),
  }).addTo(layer);

  function redraw() {
    layer.clearLayers();
    const b = map.getBounds();
    const [xW, yS] = mapToUtm(L.latLng(b.getSouth(), b.getWest()));
    const [xE, yN] = mapToUtm(L.latLng(b.getNorth(), b.getEast()));
    // label pitch: every 100 m line if they are >=45 px apart, else 500 m
    const pA = map.latLngToContainerPoint(utmToMap(META.x0, META.y0));
    const pB = map.latLngToContainerPoint(utmToMap(META.x0 + 100, META.y0));
    const px100 = Math.abs(pB.x - pA.x);
    const step = px100 >= 45 ? 100 : px100 >= 9 ? 500 : 1000;

    const latB = clamp(b.getSouth(), 0, META.height_px);
    const latT = clamp(b.getNorth(), 0, META.height_px);
    const lngL = clamp(b.getWest(), 0, META.width_px);
    const lngR = clamp(b.getEast(), 0, META.width_px);

    const x0 = Math.ceil(Math.max(xW, META.x0) / step) * step;
    for (let x = x0; x <= Math.min(xE, META.x1); x += step) {
      const lng = (x - META.x0) / (META.x1 - META.x0) * META.width_px;
      chip([latB, lng], gridLabel(x), x % 500 === 0, "bottom");
      chip([latT, lng], gridLabel(x), x % 500 === 0, "top");
    }
    const y0 = Math.ceil(Math.max(yS, META.y0) / step) * step;
    for (let y = y0; y <= Math.min(yN, META.y1); y += step) {
      const lat = (y - META.y0) / (META.y1 - META.y0) * META.height_px;
      chip([lat, lngL], gridLabel(y), y % 500 === 0, "left");
      chip([lat, lngR], gridLabel(y), y % 500 === 0, "right");
    }
  }
  map.on("move zoomend viewreset resize", redraw);
  redraw();
}

// --- node state ---------------------------------------------------------
function nodeState(id) {
  let st = nodes.get(id);
  if (!st) {
    const color = PALETTE[nodes.size % PALETTE.length];
    st = { id, color, latest: null, t: 0, trail: [], history: [],
           marker: null, label: null, trailLine: null };
    nodes.set(id, st);
  }
  return st;
}

function ingest(id, rec, draw = true) {
  const p = rec.parameters;
  if (!validFix(p)) return;
  const t = Date.parse(rec.timestamp);
  const st = nodeState(id);
  if (t <= st.t) return;                       // not newer than what we have
  const [x, y] = llToUtm(p.gps_lat, p.gps_lon);
  const fix = { ...p, x, y, lat: p.gps_lat, lon: p.gps_lon, t };
  st.history.push(fix);
  if (st.history.length > HISTORY_MAX) st.history.shift();
  st.latest = fix;
  st.t = t;
  if (onMap(x, y)) {
    st.trail.push(utmToMap(x, y));
    if (st.trail.length > TRAIL_MAX) st.trail.shift();
  }
  if (draw) drawNode(st);
}

function popupHtml(st) {
  const l = st.latest;
  return `<b>Node ${st.id}</b><br>
    <code>${usngFull(l.x, l.y)}</code><br>
    square <b>${usngSquare(l.x, l.y)}</b><br>
    ${l.lat.toFixed(6)}, ${l.lon.toFixed(6)}<br>
    battery: ${l.battery_volts ?? "?"} V · rssi: ${l.rssi ?? "?"}<br>
    ${new Date(l.t).toLocaleString()}`;
}

function drawNode(st) {
  if (!st.trailLine) {
    st.trailLine = L.polyline([], {
      color: st.color, weight: 2, opacity: 0.6, dashArray: "4 4",
    }).addTo(map);
  }
  st.trailLine.setLatLngs(st.trail);

  const l = st.latest;
  if (!l || !onMap(l.x, l.y)) {
    if (st.marker) { st.marker.remove(); st.marker = null; }
    if (st.label) { st.label.remove(); st.label = null; }
    return;
  }
  const pos = utmToMap(l.x, l.y);
  if (!st.marker) {
    st.marker = L.circleMarker(pos, {
      radius: 9, color: "#111", weight: 2,
      fillColor: st.color, fillOpacity: 0.95,
    }).addTo(map).bindPopup(() => popupHtml(st));
    const icon = LABEL_STYLE === "ondot"
      ? L.divIcon({ className: "", iconSize: null, html:
          `<div class="node-num">${st.id}</div>` })
      : L.divIcon({ className: "", html:
          `<div class="node-label" style="border-color:${st.color}">${st.id}</div>`,
          iconAnchor: [-8, 22] });
    st.label = L.marker(pos, { icon, interactive: false, keyboard: false })
      .addTo(map);
  } else {
    st.marker.setLatLng(pos);
    st.label.setLatLng(pos);
  }
  const stale = nowMs() - l.t > STALE_MS;
  st.marker.setStyle({ fillOpacity: stale ? 0.35 : 0.95 });
}

// --- goal markers ---------------------------------------------------------
function drawGoals() {
  for (const g of GOALS) {
    const color = nodes.get(g.node)?.color ?? "#111";
    const [e3, n3] = g.square.split("-").map(Number);
    const x = Math.floor(META.x0 / 100000) * 100000 + e3 * 100;  // SW corner
    const y = Math.floor(META.y0 / 100000) * 100000 + n3 * 100;
    const label = `Node ${g.node} goal — square <b>${g.square}</b>`;
    L.rectangle([utmToMap(x, y), utmToMap(x + 100, y + 100)], {
      color, weight: 2.5, dashArray: "6 4", fill: true, fillOpacity: 0.08,
    }).addTo(map).bindPopup(label);
    L.marker(utmToMap(x + 50, y + 50), {
      interactive: false, keyboard: false,
      icon: L.divIcon({ className: "", iconSize: null, html:
        `<div class="goal-star" style="color:${color}">★</div>` }),
    }).addTo(map);
  }
}

// --- sidebar ------------------------------------------------------------
function renderSidebar() {
  const items = [...nodes.values()].sort((a, b) => a.id - b.id);
  nodesEl.innerHTML = items.map((st) => {
    if (!st.latest) return "";
    const l = st.latest;
    const stale = nowMs() - l.t > STALE_MS;
    const off = !onMap(l.x, l.y);
    return `<div class="node ${stale ? "stale" : ""}" data-id="${st.id}">
      <div class="hdr"><span class="dot" style="background:${st.color}"></span>
        Node ${st.id} ${off ? '<span class="offmap">— OFF MAP</span>' : ""}</div>
      <div class="usng">${usngSquare(l.x, l.y)}</div>
      <div class="meta">${agoText(l.t)} · ${l.battery_volts ?? "?"} V<br>
        ${l.lat.toFixed(5)}, ${l.lon.toFixed(5)}</div>
    </div>`;
  }).join("") || "<i>no nodes with a GPS fix yet</i>";
}
nodesEl.addEventListener("click", (e) => {
  const el = e.target.closest(".node");
  if (!el) return;
  const st = nodes.get(Number(el.dataset.id));
  if (st?.marker) { map.panTo(st.marker.getLatLng()); st.marker.openPopup(); }
});

// --- replay (static data mode) -------------------------------------------
function setTime(T) {
  replayT = T;
  for (const st of nodes.values()) {
    let last = null;
    const trail = [];
    for (const h of st.history) {
      if (h.t > T) break;
      last = h;
      if (onMap(h.x, h.y)) trail.push(utmToMap(h.x, h.y));
    }
    if (trail.length > TRAIL_MAX) trail.splice(0, trail.length - TRAIL_MAX);
    st.latest = last;
    st.t = last ? last.t : 0;
    st.trail = trail;
    drawNode(st);
  }
  renderSidebar();
  document.getElementById("timelabel").textContent =
    new Date(T).toLocaleString();
}

function buildReplayUI(t0, t1) {
  const div = document.createElement("div");
  div.id = "replay";
  div.innerHTML = `
    <div class="row">
      <button id="play" title="play/pause">▶</button>
      <input id="timeslider" type="range" min="${t0}" max="${t1}"
             value="${t1}" step="1000">
    </div>
    <div id="timelabel"></div>`;
  statusEl.after(div);

  const slider = document.getElementById("timeslider");
  const playBtn = document.getElementById("play");
  slider.addEventListener("input", () => setTime(+slider.value));

  let timer = null;
  const stop = () => { clearInterval(timer); timer = null; playBtn.textContent = "▶"; };
  playBtn.addEventListener("click", () => {
    if (timer) { stop(); return; }
    if (+slider.value >= t1) slider.value = t0;
    const step = Math.max(1000, (t1 - t0) / 300);   // whole span in ~30 s
    playBtn.textContent = "⏸";
    timer = setInterval(() => {
      slider.value = Math.min(t1, +slider.value + step);
      setTime(+slider.value);
      if (+slider.value >= t1) stop();
    }, 100);
  });
}

async function loadStatic() {
  const feed = await fetchJson(DATA_URL);
  const recs = feed.data.filter((r) => validFix(r.parameters));
  recs.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  for (const rec of recs) ingest(rec.parameters.node_id, rec, false);
  if (!recs.length) {
    setStatus("archive is empty — no GPS fixes in data file", true);
    renderSidebar();
    return;
  }
  const t0 = Date.parse(recs[0].timestamp);
  const t1 = Date.parse(recs[recs.length - 1].timestamp);
  buildReplayUI(t0, t1);
  setTime(t1);
  setStatus(`archive · ${nodes.size} node(s) · ${recs.length} fixes · ` +
            `${new Date(t0).toLocaleDateString()}–${new Date(t1).toLocaleDateString()}`);
}

// --- live feed polling ----------------------------------------------------
async function fetchJson(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

async function rescan() {
  const feed = await fetchJson(`${FEED}/json/`);
  const recs = feed.data.filter((r) => validFix(r.parameters));
  recs.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  for (const rec of recs) ingest(rec.parameters.node_id, rec);
}

async function pollLatest() {
  await Promise.all([...nodes.keys()].map(async (id) => {
    const feed = await fetchJson(`${FEED}/latest/${id}`);
    for (const rec of feed.data) ingest(id, rec);
  }));
}

let busy = false;
async function tick(fn) {
  if (busy) return;
  busy = true;
  try {
    await fn();
    setStatus(`live · ${nodes.size} node(s) · updated ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    setStatus(`feed error: ${err.message}`, true);
  } finally {
    busy = false;
    renderSidebar();
  }
}

// --- boot ---------------------------------------------------------------
(async () => {
  META = await (await fetch(`${BASE}.json`)).json();
  const bounds = [[0, 0], [META.height_px, META.width_px]];
  map = L.map("map", { crs: L.CRS.Simple, minZoom: -2, maxZoom: 3,
                       zoomSnap: 0.25, attributionControl: false });
  L.imageOverlay(`${BASE}.png`, bounds).addTo(map);
  map.fitBounds(bounds);
  map.setMaxBounds(L.latLngBounds(bounds).pad(0.25));

  if (dynamicGridLabels) setupGridLabels();

  const readout = document.getElementById("readout");
  const showUtm = (latlng) => {
    const [x, y] = mapToUtm(latlng);
    readout.textContent = onMap(x, y)
      ? `${usngFull(x, y)}  ·  square ${usngSquare(x, y)}`
      : "outside map";
  };
  map.on("click", (e) => showUtm(e.latlng));
  map.on("mousemove", (e) => showUtm(e.latlng));

  if (DATA_URL) {
    setStatus("loading archive…");
    await loadStatic();
  } else {
    setStatus("fetching feed…");
    await tick(rescan);
    setInterval(() => tick(pollLatest), POLL_LATEST_MS);
    setInterval(() => tick(rescan), RESCAN_MS);
    setInterval(renderSidebar, 5000);   // keep the "N s ago" text fresh
  }
  drawGoals();   // after data load so goal colors match node colors
})().catch((err) => setStatus(`init failed: ${err.message}`, true));
