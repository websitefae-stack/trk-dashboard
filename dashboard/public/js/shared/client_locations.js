(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    if (window.frappe && window.frappe.csrf_token) return window.frappe.csrf_token;
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  async function callApi(method, payload) {
    var response = await fetch("/api/method/" + method, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    var data = await response.json();

    if (!response.ok || data.exc) {
      console.error(data);
      throw new Error(data.message || "Request failed.");
    }

    return data.message || data;
  }

  function csvCell(value) {
    var text = String(value == null ? "" : value).replace(/"/g, '""');
    return '"' + text + '"';
  }

  function exportRowsToCsv(filename, columns, rows) {
    if (!rows || !rows.length) {
      window.alert("Run the report first.");
      return;
    }

    var lines = [columns.map(function (c) { return csvCell(c.label); }).join(",")];

    rows.forEach(function (row) {
      lines.push(columns.map(function (c) { return csvCell(c.value(row)); }).join(","));
    });

    var blob = new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);

    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  var state = { rows: [], map: null, markerLayer: null };

  function renderTable(rows) {
    var body = el("clientLocationsTableBody");
    if (!body) return;

    body.innerHTML = rows.map(function (row) {
      return "<tr>"
        + "<td>" + escapeHtml(row.client_label || row.client) + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.client_postcode || "—") + "</td>"
        + "<td>" + escapeHtml(row.therapy_postcode || "—") + "</td>"
        + "</tr>";
    }).join("");
  }

  function ensureMap() {
    if (state.map || !window.L) return state.map;

    var mapEl = el("clientLocationsMap");
    if (!mapEl) return null;

    state.map = window.L.map(mapEl).setView([54.5, -3], 6);

    window.L.Icon.Default.mergeOptions({
      iconUrl: "/assets/dashboard/vendor/leaflet/images/marker-icon.png",
      iconRetinaUrl: "/assets/dashboard/vendor/leaflet/images/marker-icon-2x.png",
      shadowUrl: "/assets/dashboard/vendor/leaflet/images/marker-shadow.png"
    });

    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(state.map);

    state.markerLayer = window.L.layerGroup().addTo(state.map);

    return state.map;
  }

  // postcodes.io's bulk lookup takes up to 100 postcodes per request - chunk
  // accordingly rather than assuming every report run stays under that.
  async function geocodePostcodes(postcodes) {
    var unique = Array.from(new Set(postcodes.map(function (p) { return p.trim().toUpperCase(); }).filter(Boolean)));
    var results = {};

    for (var i = 0; i < unique.length; i += 100) {
      var chunk = unique.slice(i, i + 100);

      try {
        var response = await fetch("https://api.postcodes.io/postcodes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ postcodes: chunk })
        });

        var data = await response.json();

        (data.result || []).forEach(function (entry) {
          if (entry.result && entry.result.latitude != null && entry.result.longitude != null) {
            results[entry.query.trim().toUpperCase()] = [entry.result.latitude, entry.result.longitude];
          }
        });
      } catch (error) {
        console.error("Postcode lookup failed:", error);
      }
    }

    return results;
  }

  async function plotMap(rows) {
    var map = ensureMap();
    var note = el("clientLocationsMapNote");
    if (!map) {
      if (note) {
        note.style.display = "";
        note.textContent = "Map could not be loaded.";
      }
      return;
    }

    state.markerLayer.clearLayers();

    var postcodes = [];
    rows.forEach(function (row) {
      if (row.client_postcode) postcodes.push(row.client_postcode);
      if (row.therapy_postcode) postcodes.push(row.therapy_postcode);
    });

    if (!postcodes.length) {
      if (note) {
        note.style.display = "";
        note.textContent = "No postcodes to plot.";
      }
      return;
    }

    var coords = await geocodePostcodes(postcodes);
    var bounds = [];
    var missed = 0;

    rows.forEach(function (row) {
      [
        { postcode: row.client_postcode, label: "Home" },
        { postcode: row.therapy_postcode, label: "Therapy Location" }
      ].forEach(function (entry) {
        if (!entry.postcode) return;

        var key = entry.postcode.trim().toUpperCase();
        var point = coords[key];

        if (!point) {
          missed += 1;
          return;
        }

        window.L.marker(point)
          .addTo(state.markerLayer)
          .bindPopup(
            "<strong>" + escapeHtml(row.client_label || row.client) + "</strong><br>"
            + escapeHtml(row.coach_label || "") + "<br>"
            + escapeHtml(entry.label) + ": " + escapeHtml(entry.postcode)
          );

        bounds.push(point);
      });
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }

    if (note) {
      if (missed) {
        note.style.display = "";
        note.textContent = missed + " postcode(s) could not be located on the map.";
      } else {
        note.style.display = "none";
      }
    }

    // Leaflet sizes its canvas from the container's dimensions at creation
    // time - this tab/card can be hidden (display:none) when the map first
    // initialises, so it always needs a resize nudge once it's visible.
    setTimeout(function () { map.invalidateSize(); }, 0);
  }

  async function loadCoachOptions() {
    var select = el("clientLocationsCoachSelect");
    if (!select) return;

    try {
      var options = await callApi("dashboard.api.shared.coach_logs.get_coach_log_options", {});

      (options || []).forEach(function (opt) {
        var optionEl = document.createElement("option");
        optionEl.value = opt.value;
        optionEl.textContent = opt.label;
        select.appendChild(optionEl);
      });
    } catch (error) {
      console.error("Coach options failed:", error);
    }
  }

  async function runReport() {
    var btn = el("runClientLocationsReportBtn");
    var select = el("clientLocationsCoachSelect");
    var empty = el("clientLocationsEmpty");
    var results = el("clientLocationsResults");
    var exportBtn = el("exportClientLocationsReportBtn");

    if (btn) { btn.disabled = true; btn.textContent = "Running..."; }

    try {
      var rows = await callApi("dashboard.api.shared.client_locations.get_client_locations_report", {
        coach: select ? select.value : ""
      });

      state.rows = rows || [];

      if (!rows.length) {
        if (empty) { empty.style.display = ""; empty.textContent = "No clients with a postcode found."; }
        if (results) results.style.display = "none";
        if (exportBtn) exportBtn.style.display = "none";
        return;
      }

      if (empty) empty.style.display = "none";
      if (results) results.style.display = "";
      if (exportBtn) exportBtn.style.display = "";

      renderTable(rows);
      await plotMap(rows);
    } catch (error) {
      window.alert(error.message || "Could not run the report.");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Run Report"; }
    }
  }

  function exportReport() {
    exportRowsToCsv("client-locations.csv", [
      { label: "Client", value: function (r) { return r.client_label || r.client; } },
      { label: "Coach", value: function (r) { return r.coach_label || ""; } },
      { label: "Client Postcode", value: function (r) { return r.client_postcode || ""; } },
      { label: "Therapy Location Postcode", value: function (r) { return r.therapy_postcode || ""; } }
    ], state.rows);
  }

  function init() {
    if (!el("runClientLocationsReportBtn")) return;

    loadCoachOptions();

    el("runClientLocationsReportBtn").addEventListener("click", runReport);

    var exportBtn = el("exportClientLocationsReportBtn");
    if (exportBtn) exportBtn.addEventListener("click", exportReport);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
