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

  var state = { rows: [], territories: {}, coachLabelByName: {}, map: null, markerLayer: null, territoryLayer: null };

  var TERRITORY_BOUNDARY_COLOR = "#D7263D";

  function areaCheckLabel(row) {
    if (row.in_area === true) return "In area";
    if (row.in_area === false) {
      return row.other_coach_label ? "In " + row.other_coach_label + "'s area" : "Out of area";
    }
    return "—";
  }

  function renderTable(rows) {
    var body = el("clientLocationsTableBody");
    if (!body) return;

    body.innerHTML = rows.map(function (row) {
      var flagged = row.in_area === false;

      return "<tr>"
        + "<td>" + escapeHtml(row.client_label || row.client) + "</td>"
        + "<td>" + escapeHtml(row.coach_label || "—") + "</td>"
        + "<td>" + escapeHtml(row.client_postcode || "—") + "</td>"
        + "<td>" + escapeHtml(row.therapy_postcode || "—") + "</td>"
        + "<td" + (flagged ? ' style="color:#c0392b;font-weight:700;"' : "") + ">" + escapeHtml(areaCheckLabel(row)) + "</td>"
        + "</tr>";
    }).join("");
  }

  function ensureMap() {
    if (state.map || !window.L) return state.map;

    var mapEl = el("clientLocationsMap");
    if (!mapEl) return null;

    state.map = window.L.map(mapEl).setView([54.5, -3], 6);

    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(state.map);

    state.markerLayer = window.L.layerGroup().addTo(state.map);
    state.territoryLayer = window.L.layerGroup().addTo(state.map);

    // Leaflet's zoom control and attribution links are <a href="#"> - it
    // prevents their own default navigation internally, but belt-and-braces
    // this stops ANY stray href="#" click inside the map (however it got
    // there) from falling through to the browser's default "jump to top of
    // page" behaviour for an empty-fragment link.
    mapEl.addEventListener("click", function (event) {
      var anchor = event.target.closest("a");
      if (anchor && (anchor.getAttribute("href") === "#" || anchor.getAttribute("href") === "")) {
        event.preventDefault();
      }
    }, true);

    return state.map;
  }

  // Small, high-contrast palette so each coach's pins are visually distinct
  // on the map - deterministic (same coach always gets the same colour
  // across report runs) via a simple string hash rather than assignment
  // order, which would shuffle colours whenever the coach list changes.
  var PIN_COLORS = [
    "#E4572E", "#17BEBB", "#2E86AB", "#A23B72", "#F18F01",
    "#6A994E", "#8338EC", "#D62839", "#3A86FF", "#B5838D"
  ];

  function colorForCoach(label) {
    var text = label || "Unassigned";
    var hash = 0;
    for (var i = 0; i < text.length; i++) {
      hash = (hash * 31 + text.charCodeAt(i)) & 0xffffffff;
    }
    return PIN_COLORS[Math.abs(hash) % PIN_COLORS.length];
  }

  var OUT_OF_AREA_COLOR = "#1a1a1a";

  function pinIcon(color, flagged) {
    var center = flagged
      ? '<path d="M13 8.5v6M13 18.2v.1" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>'
      : '<circle cx="13" cy="13" r="4.5" fill="#ffffff"/>';

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="26" height="36" viewBox="0 0 26 36">'
      + '<path d="M13 0C5.82 0 0 5.82 0 13c0 9.75 13 23 13 23s13-13.25 13-23C26 5.82 20.18 0 13 0z" '
      + 'fill="' + color + '" stroke="#ffffff" stroke-width="1.5"/>'
      + center
      + '</svg>';

    return window.L.divIcon({
      className: "trk-map-pin",
      html: svg,
      iconSize: [26, 36],
      iconAnchor: [13, 34],
      popupAnchor: [0, -30]
    });
  }

  // Andrew's monotone chain - a simple, dependency-free convex hull over
  // [lat, lng] pairs treated as plain 2D coordinates. Fine as a visual
  // "roughly this area" boundary at UK scale; not a geodesically precise
  // shape, and not the real administrative postcode-area boundary (this
  // app has no access to that boundary data) - just a hull around the
  // coach's own actual client/therapy-location points.
  function convexHull(points) {
    var pts = points.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    if (pts.length < 3) return pts;

    function cross(o, a, b) {
      return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    }

    var lower = [];
    for (var i = 0; i < pts.length; i++) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pts[i]) <= 0) {
        lower.pop();
      }
      lower.push(pts[i]);
    }

    var upper = [];
    for (var j = pts.length - 1; j >= 0; j--) {
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pts[j]) <= 0) {
        upper.pop();
      }
      upper.push(pts[j]);
    }

    upper.pop();
    lower.pop();
    return lower.concat(upper);
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

  // Territory Postcode Areas entries are outward-code prefixes, sometimes
  // with a sector digit attached (e.g. "SK10 5", not just "SK10") - the
  // sector digit isn't something postcodes.io's outcode endpoint
  // understands, so this strips it back down to the plain outward code
  // ("SK10") for geocoding. Good enough for a visual "roughly this area"
  // boundary; not sector-precise.
  function territoryOutcode(prefix) {
    var trimmed = (prefix || "").trim().toUpperCase();
    var spaceIdx = trimmed.indexOf(" ");
    return spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx);
  }

  // postcodes.io has no bulk endpoint for outward codes (only full
  // postcodes), so these go one request per unique outcode - in practice a
  // coach's territory list is a handful of entries, not hundreds.
  async function geocodeOutcodes(outcodes) {
    var unique = Array.from(new Set(outcodes.filter(Boolean)));
    var results = {};

    await Promise.all(unique.map(async function (outcode) {
      try {
        var response = await fetch("https://api.postcodes.io/outcodes/" + encodeURIComponent(outcode));
        var data = await response.json();

        if (data && data.result && data.result.latitude != null && data.result.longitude != null) {
          results[outcode] = [data.result.latitude, data.result.longitude];
        }
      } catch (error) {
        console.error("Outcode lookup failed:", error);
      }
    }));

    return results;
  }

  // Draws the coach's *assigned* Territory Postcode Areas as a thick red
  // outline - deliberately distinct from the thin, coach-coloured hull
  // drawn around a coach's actual client points further down, since that
  // one only shows where existing clients happen to be, not where the
  // coach is meant to be covering. This is the one that answers "is this
  // client out of area" against the area itself.
  async function plotTerritoryBoundaries(territories) {
    var coachNames = Object.keys(territories || {});
    if (!coachNames.length) return;

    var outcodesByCoach = {};
    var allOutcodes = [];

    coachNames.forEach(function (coachName) {
      var outcodes = Array.from(new Set((territories[coachName] || []).map(territoryOutcode).filter(Boolean)));
      outcodesByCoach[coachName] = outcodes;
      allOutcodes = allOutcodes.concat(outcodes);
    });

    var coords = await geocodeOutcodes(allOutcodes);

    coachNames.forEach(function (coachName) {
      var label = state.coachLabelByName[coachName] || coachName;
      var points = outcodesByCoach[coachName]
        .map(function (outcode) { return coords[outcode]; })
        .filter(Boolean);

      if (points.length >= 3) {
        var hull = convexHull(points);
        window.L.polygon(hull, {
          color: TERRITORY_BOUNDARY_COLOR,
          weight: 4,
          opacity: 0.9,
          fillOpacity: 0.04
        })
          .addTo(state.territoryLayer)
          .bindPopup(escapeHtml(label) + "'s assigned area");
      } else if (points.length === 2) {
        window.L.polyline(points, { color: TERRITORY_BOUNDARY_COLOR, weight: 4, opacity: 0.9 })
          .addTo(state.territoryLayer)
          .bindPopup(escapeHtml(label) + "'s assigned area");
      } else if (points.length === 1) {
        window.L.circle(points[0], {
          radius: 3000,
          color: TERRITORY_BOUNDARY_COLOR,
          weight: 4,
          opacity: 0.9,
          fillOpacity: 0.04
        })
          .addTo(state.territoryLayer)
          .bindPopup(escapeHtml(label) + "'s assigned area (approximate)");
      }
    });
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
    state.territoryLayer.clearLayers();

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
    var pointsByCoach = {};

    rows.forEach(function (row) {
      var flagged = row.in_area === false;
      var color = flagged ? OUT_OF_AREA_COLOR : colorForCoach(row.coach_label);

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

        var popupLines = [
          "<strong>" + escapeHtml(row.client_label || row.client) + "</strong>",
          escapeHtml(row.coach_label || ""),
          escapeHtml(entry.label) + ": " + escapeHtml(entry.postcode)
        ];

        if (flagged) {
          popupLines.push(
            '<span style="color:#c0392b;font-weight:700;">'
            + escapeHtml(areaCheckLabel(row)) + "</span>"
          );
        }

        window.L.marker(point, { icon: pinIcon(color, flagged) })
          .addTo(state.markerLayer)
          .bindPopup(popupLines.join("<br>"));

        bounds.push(point);

        // Only in-area points contribute to a coach's territory outline -
        // an out-of-area client's point shouldn't stretch their own
        // coach's boundary out to cover them, that's the whole point of
        // flagging it.
        if (row.in_area !== false && row.coach_label) {
          if (!pointsByCoach[row.coach_label]) pointsByCoach[row.coach_label] = [];
          pointsByCoach[row.coach_label].push(point);
        }
      });
    });

    // A coach with an assigned Territory Postcode Areas boundary gets that
    // one drawn instead (thick red, plotted below) - this thin coach-
    // coloured hull is only a fallback for coaches nobody has set a
    // territory for yet, where "where their clients happen to be" is all
    // there is to go on.
    var labelsWithTerritory = {};
    Object.keys(state.territories || {}).forEach(function (coachName) {
      labelsWithTerritory[state.coachLabelByName[coachName] || coachName] = true;
    });

    Object.keys(pointsByCoach).forEach(function (coachLabel) {
      if (labelsWithTerritory[coachLabel]) return;

      var pts = pointsByCoach[coachLabel];
      if (pts.length < 3) return;

      var hull = convexHull(pts);
      window.L.polygon(hull, {
        color: colorForCoach(coachLabel),
        weight: 2,
        fillOpacity: 0.08
      })
        .addTo(state.territoryLayer)
        .bindPopup(escapeHtml(coachLabel) + "'s area");
    });

    await plotTerritoryBoundaries(state.territories);

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

    try {
      var options = await callApi("dashboard.api.shared.coach_logs.get_coach_log_options", {});

      (options || []).forEach(function (opt) {
        state.coachLabelByName[opt.value] = opt.label;

        if (select) {
          var optionEl = document.createElement("option");
          optionEl.value = opt.value;
          optionEl.textContent = opt.label;
          select.appendChild(optionEl);
        }
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
      var payload = await callApi("dashboard.api.shared.client_locations.get_client_locations_report", {
        coach: select ? select.value : ""
      });

      var rows = (payload && payload.rows) || [];
      state.rows = rows;
      state.territories = (payload && payload.territories) || {};

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
      { label: "Therapy Location Postcode", value: function (r) { return r.therapy_postcode || ""; } },
      { label: "Area Check", value: function (r) { return areaCheckLabel(r); } }
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
