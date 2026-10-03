// Lead map: pins by stage + cuisine icon, clustering, time slider, radius filter (PRD M2-M5).
(function () {
  "use strict";
  const el = document.getElementById("map");
  const listEl = document.getElementById("list");
  const countEl = document.querySelector('[data-testid="map-count"]');
  const unplacedEl = document.querySelector('[data-testid="map-unplaced"]');
  const slider = document.getElementById("slider");
  const sliderLabel = document.getElementById("slider-label");
  const playBtn = document.getElementById("play");
  const f = {
    stage: document.getElementById("f-stage"),
    type: document.getElementById("f-type"),
    since: document.getElementById("f-since"),
    center: document.getElementById("f-center"),
    radius: document.getElementById("f-radius"),
  };
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const today = parseISO(el.dataset.today);
  const [cLat, cLng] = el.dataset.center.split(",").map(Number);

  const map = L.map(el, { zoomControl: true, scrollWheelZoom: true, maxZoom: 19 }).setView([cLat, cLng], 10);
  if (el.dataset.tiles) {
    L.tileLayer(el.dataset.tiles, {
      attribution: el.dataset.attribution, maxZoom: 19,
    }).addTo(map);
  }
  const cluster = L.markerClusterGroup({
    showCoverageOnHover: false, maxClusterRadius: 45, spiderfyOnMaxZoom: true,
    disableClusteringAtZoom: 15,
    iconCreateFunction: (c) => L.divIcon({
      html: `<div class="cluster">${c.getChildCount()}</div>`, className: "", iconSize: [38, 38],
    }),
  }).addTo(map);
  let circle = null;
  let customCenter = null;
  let leads = [];
  let unplacedLeads = [];
  const markers = new Map();

  function parseISO(s) { const [y, m, d] = s.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); }
  function addDays(date, n) { return new Date(date.getTime() + n * 86400000); }
  function iso(date) { return date.toISOString().slice(0, 10); }
  function label(date) { return `${MONTHS[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`; }
  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function miles(a, b) {
    const R = 3958.8, rad = (x) => (x * Math.PI) / 180;
    const dLat = rad(b[0] - a[0]), dLng = rad(b[1] - a[1]);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLng / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function pinClass(l) {
    return `pin ${l.stage === "Applied" ? "applied" : "licensed"}${l.lead_type === "ownership_change" ? " owner" : ""}`;
  }
  function popupHtml(l) {
    const when = l.stage === "Licensed"
      ? `Licensed · ${esc(l.days_ahead_label)}` : `In plan review since ${esc(l.first_seen_label)}`;
    return `<div class="popup" data-testid="map-popup">
      <div class="popup-head"><span class="popup-icon">${l.icon}</span><strong>${esc(l.name)}</strong></div>
      <div class="popup-meta">${esc(l.type_label)} · ${when}</div>
      <div>${esc(l.address)}, ${esc(l.city)}</div>
      ${l.phone ? `<div>${esc(l.phone)}</div>` : ""}${l.email ? `<div>${esc(l.email)}</div>` : ""}
      <a data-testid="map-popup-link" href="/leads/${l.id}">Open lead &rarr;</a></div>`;
  }

  function centerPoint() {
    if (f.center.value === "custom") return customCenter;
    if (!f.center.value) return null;
    return f.center.value.split(",").map(Number);
  }

  function passesBase(l) {
    const through = addDays(today, -Number(slider.value));
    const sinceDays = Number(f.since.value);
    const from = sinceDays ? addDays(today, -sinceDays) : null;
    const seen = parseISO(l.first_seen);
    if (seen > through) return false;
    if (from && seen < from) return false;
    if (f.stage.value !== "All" && l.stage !== f.stage.value) return false;
    if (f.type.value !== "All" && l.lead_type !== f.type.value) return false;
    return true;
  }

  function visible() {
    const center = centerPoint();
    const radius = f.radius.value === "Off" ? null : Number(f.radius.value);
    return leads.filter((l) => {
      if (!passesBase(l)) return false;
      if (center && radius && miles(center, [l.lat, l.lng]) > radius) return false;
      return true;
    });
  }

  function render() {
    const through = addDays(today, -Number(slider.value));
    sliderLabel.textContent = `Through ${label(through)}`;
    const shown = visible();
    cluster.clearLayers();
    shown.forEach((l) => cluster.addLayer(markers.get(l.id)));
    el.dataset.visibleIds = shown.map((l) => l.id).sort((a, b) => a - b).join(",");
    countEl.textContent = `${shown.length} ${shown.length === 1 ? "lead" : "leads"} on the map`;
    const missing = unplacedLeads.filter(passesBase).length;
    unplacedEl.hidden = missing === 0;
    unplacedEl.textContent = `${missing} not placed`;

    const center = centerPoint();
    const radius = f.radius.value === "Off" ? null : Number(f.radius.value);
    if (circle) { map.removeLayer(circle); circle = null; }
    if (center && radius) {
      circle = L.circle(center, { radius: radius * 1609.34, color: "#111", weight: 1, fillOpacity: 0.04, dashArray: "4 4" }).addTo(map);
    }

    listEl.innerHTML = shown.length ? "" : '<p class="muted small">No leads match.</p>';
    shown.forEach((l) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "list-item";
      item.setAttribute("data-testid", "map-list-item");
      item.dataset.leadId = l.id;
      item.dataset.cuisine = l.cuisine;
      item.innerHTML = `<span class="list-icon ${l.stage === "Applied" ? "applied" : "licensed"}">${l.icon}</span>
        <span class="list-text"><strong>${esc(l.name)}</strong>
        <span class="muted small">${esc(l.city)} · ${l.stage === "Applied" ? "Plan review" : esc(l.days_ahead_label)}</span></span>`;
      item.addEventListener("click", () => {
        map.setView([l.lat, l.lng], Math.max(map.getZoom(), 15), { animate: false });
        L.popup({ minWidth: 220, offset: [0, -14] })
          .setLatLng([l.lat, l.lng]).setContent(popupHtml(l)).openOn(map);
      });
      listEl.appendChild(item);
    });
  }

  function build(data) {
    leads = data.leads.sort((a, b) => (a.first_seen < b.first_seen ? 1 : a.first_seen > b.first_seen ? -1 : a.name.localeCompare(b.name)));
    unplacedLeads = data.unplaced_leads || [];
    leads.forEach((l) => {
      const icon = L.divIcon({ className: "", html: `<div class="${pinClass(l)}">${l.icon}</div>`, iconSize: [34, 34], iconAnchor: [17, 17], popupAnchor: [0, -16] });
      const m = L.marker([l.lat, l.lng], { icon, title: l.name, riseOnHover: true });
      m.bindPopup(popupHtml(l), { closeButton: true, minWidth: 220 });
      markers.set(l.id, m);
    });
    render();
    if (leads.length) {
      const bounds = L.latLngBounds(leads.map((l) => [l.lat, l.lng]));
      map.fitBounds(bounds.pad(0.15), { maxZoom: 13 });
    }
  }

  map.on("click", (e) => {
    customCenter = [e.latlng.lat, e.latlng.lng];
    f.center.value = "custom";
    if (f.radius.value === "Off") f.radius.value = "5";
    render();
  });
  Object.values(f).forEach((s) => s.addEventListener("change", render));
  slider.addEventListener("input", render);

  let timer = null;
  playBtn.addEventListener("click", () => {
    if (timer) { clearInterval(timer); timer = null; playBtn.innerHTML = "&#9654; Play"; return; }
    slider.value = slider.max;
    render();
    playBtn.innerHTML = "&#10073;&#10073; Pause";
    timer = setInterval(() => {
      const v = Number(slider.value) - 1;
      slider.value = Math.max(v, 0);
      render();
      if (v <= 0) { clearInterval(timer); timer = null; playBtn.innerHTML = "&#9654; Play"; }
    }, 120);
  });

  fetch("/map/data.json?hidden=0").then((r) => r.json()).then(build);
})();
