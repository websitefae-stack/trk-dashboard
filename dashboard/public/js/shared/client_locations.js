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

  var state = { rows: [], territories: {}, coachLabelByName: {}, coachColorByName: {}, map: null, markerLayer: null, territoryLayer: null };

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

  var HEX_COLOR_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

  function customCoachColor(coachName) {
    var colour = state.coachColorByName[coachName];
    return colour && HEX_COLOR_RE.test(colour) ? colour : "";
  }

  // The office-assigned Coach.colour when there is one (and it's a real hex
  // colour, not whatever was typed into that field), otherwise the same
  // deterministic hash-based colour pins/hulls have always used.
  function coachColor(coachName, label) {
    return customCoachColor(coachName) || colorForCoach(label || coachName);
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

  function computeCentroid(points) {
    if (!points.length) return null;
    var sumLat = 0, sumLng = 0;
    points.forEach(function (p) { sumLat += p[0]; sumLng += p[1]; });
    return [sumLat / points.length, sumLng / points.length];
  }

  function boundsAroundPoints(points, padDegrees) {
    var lats = points.map(function (p) { return p[0]; });
    var lngs = points.map(function (p) { return p[1]; });
    return [
      Math.min.apply(null, lngs) - padDegrees,
      Math.min.apply(null, lats) - padDegrees,
      Math.max.apply(null, lngs) + padDegrees,
      Math.max.apply(null, lats) + padDegrees
    ];
  }

  function squaredDist(a, b) {
    var dx = a[0] - b[0], dy = a[1] - b[1];
    return dx * dx + dy * dy;
  }

  // Which of point i's Delaunay neighbours (if any) this Voronoi cell edge
  // is shared with. A real shared edge sits exactly on the perpendicular
  // bisector of i and that neighbour, so its midpoint is (to floating-point
  // precision) equidistant from both - an edge produced by clipping the
  // cell to the bounding box instead never is, for any neighbour, so this
  // reliably tells the two apart without needing polygon-union geometry.
  function edgeNeighbor(midpoint, seedXY, i, neighborIndexes) {
    var di = squaredDist(midpoint, seedXY[i]);
    var best = null;
    var bestDiff = Infinity;

    neighborIndexes.forEach(function (j) {
      var diff = Math.abs(di - squaredDist(midpoint, seedXY[j]));
      if (diff < bestDiff) {
        bestDiff = diff;
        best = j;
      }
    });

    return bestDiff < 1e-9 ? best : null;
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
  // postcodes), so these go one request per unique outcode - only used now
  // as a fallback (see plotTerritoryBoundaries) when a prefix's
  // autocomplete search below comes back empty.
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

  // A single outward-code centre per prefix produces a boundary with only
  // one point per prefix - a convex hull over 3-4 such points is a huge,
  // gappy triangle, not something that reads as "this area". postcodes.io's
  // autocomplete endpoint turns a prefix like "SK10 5" (or a bare "N1")
  // into a handful of real postcodes that actually exist inside it, which
  // geocode to points scattered across the real area instead of its centre
  // alone - a hull over those hugs the actual shape far more closely and
  // naturally joins up neighbouring prefixes into one connected outline.
  async function autocompletePostcodes(prefix) {
    try {
      var response = await fetch(
        "https://api.postcodes.io/postcodes/" + encodeURIComponent(prefix) + "/autocomplete?limit=10"
      );
      var data = await response.json();
      return (data && data.result) || [];
    } catch (error) {
      console.error("Postcode autocomplete failed:", error);
      return [];
    }
  }

  // Single-point-per-coach fallback (a plain circle) - only reached when
  // there aren't enough territory points site-wide for a Voronoi diagram to
  // mean anything (fewer than 2), or the d3-delaunay bundle didn't load.
  function plotTerritoryBoundariesFallback(coachNames, centroidByPrefix, prefixesByCoach) {
    coachNames.forEach(function (coachName) {
      var label = state.coachLabelByName[coachName] || coachName;
      var color = customCoachColor(coachName) || TERRITORY_BOUNDARY_COLOR;
      var points = (prefixesByCoach[coachName] || [])
        .map(function (prefix) { return centroidByPrefix[prefix]; })
        .filter(Boolean);

      if (!points.length) return;

      var point = computeCentroid(points);
      window.L.circle(point, {
        radius: 3000,
        color: color,
        weight: 4,
        opacity: 0.9,
        fillOpacity: 0.18
      })
        .addTo(state.territoryLayer)
        .bindPopup(escapeHtml(label) + "'s assigned area (approximate)");
    });
  }

  // Draws each coach's *assigned* Territory Postcode Areas as a filled,
  // labelled region in their own colour (see coachColor()/customCoachColor()).
  //
  // Rather than a convex hull around a handful of centre points (which can
  // only ever bulge outward, never fit a real coastline or dip inward
  // between two coaches - see the git history of this function for that
  // earlier attempt), this tessellates a Voronoi diagram over every
  // coach's postcode-area points *site-wide* and gives each coach the
  // cells belonging to their own points. Two coaches' points always end up
  // with a shared, gap-free border between their cells - exactly the
  // "areas fit together like puzzle pieces" look a real postcode-boundary
  // map (e.g. Vision's) has, without needing real GIS boundary data this
  // app has no access to. It's still an approximation: a Voronoi cell is
  // "closer to this point than any other claimed point", not the true
  // legal shape of a postcode sector, and a sector nobody has claimed gets
  // silently absorbed into whichever claimed neighbour is nearest.
  async function plotTerritoryBoundaries(territories) {
    var coachNames = Object.keys(territories || {});
    if (!coachNames.length) return;

    var prefixesByCoach = {};
    var allPrefixes = [];
    var coachOfPrefix = {};

    coachNames.forEach(function (coachName) {
      var prefixes = Array.from(new Set((territories[coachName] || []).map(function (p) { return (p || "").trim().toUpperCase(); }).filter(Boolean)));
      prefixesByCoach[coachName] = prefixes;
      allPrefixes = allPrefixes.concat(prefixes);
      prefixes.forEach(function (prefix) { coachOfPrefix[prefix] = coachName; });
    });

    var uniquePrefixes = Array.from(new Set(allPrefixes));

    var samplesByPrefix = {};
    await Promise.all(uniquePrefixes.map(async function (prefix) {
      samplesByPrefix[prefix] = await autocompletePostcodes(prefix);
    }));

    var allSamples = [];
    Object.keys(samplesByPrefix).forEach(function (prefix) {
      allSamples = allSamples.concat(samplesByPrefix[prefix]);
    });

    var fallbackOutcodes = uniquePrefixes
      .filter(function (prefix) { return !samplesByPrefix[prefix].length; })
      .map(territoryOutcode);

    var pointCoords = await geocodePostcodes(allSamples);
    var outcodeCoords = fallbackOutcodes.length ? await geocodeOutcodes(fallbackOutcodes) : {};

    // One representative seed point per prefix - the centre of its
    // sampled real postcodes (see autocompletePostcodes() above), or the
    // plain district centre if none resolved.
    var centroidByPrefix = {};
    uniquePrefixes.forEach(function (prefix) {
      var samples = samplesByPrefix[prefix] || [];
      var points = samples.map(function (postcode) { return pointCoords[postcode.trim().toUpperCase()]; }).filter(Boolean);

      if (points.length) {
        centroidByPrefix[prefix] = computeCentroid(points);
      } else if (outcodeCoords[territoryOutcode(prefix)]) {
        centroidByPrefix[prefix] = outcodeCoords[territoryOutcode(prefix)];
      }
    });

    var seeds = uniquePrefixes
      .map(function (prefix) { return { coachName: coachOfPrefix[prefix], point: centroidByPrefix[prefix] }; })
      .filter(function (s) { return !!s.point; });

    if (seeds.length < 2 || !window.d3 || !window.d3.Delaunay) {
      plotTerritoryBoundariesFallback(coachNames, centroidByPrefix, prefixesByCoach);
      return;
    }

    // x/y here is lng/lat (Delaunay/Voronoi don't care about map
    // projections, just relative position) - flipped back to Leaflet's
    // [lat, lng] only when a ring/segment is actually drawn.
    var seedXY = seeds.map(function (s) { return [s.point[1], s.point[0]]; });
    var bounds = boundsAroundPoints(seeds.map(function (s) { return s.point; }), 0.08);

    var delaunay = window.d3.Delaunay.from(seedXY);
    var voronoi = delaunay.voronoi(bounds);

    var cellIndexesByCoach = {};
    seeds.forEach(function (seed, i) {
      if (!cellIndexesByCoach[seed.coachName]) cellIndexesByCoach[seed.coachName] = [];
      cellIndexesByCoach[seed.coachName].push(i);
    });

    coachNames.forEach(function (coachName) {
      var cellIndexes = cellIndexesByCoach[coachName];
      if (!cellIndexes || !cellIndexes.length) return;

      var label = state.coachLabelByName[coachName] || coachName;
      var color = customCoachColor(coachName) || TERRITORY_BOUNDARY_COLOR;

      var fillRings = [];
      var borderSegments = [];

      cellIndexes.forEach(function (i) {
        var ring = voronoi.cellPolygon(i);
        if (!ring || ring.length < 4) return;

        fillRings.push(ring.map(function (p) { return [p[1], p[0]]; }));

        var neighborIndexes = Array.from(delaunay.neighbors(i));

        for (var e = 0; e < ring.length - 1; e++) {
          var p1 = ring[e];
          var p2 = ring[e + 1];
          var midpoint = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2];
          var neighborI = edgeNeighbor(midpoint, seedXY, i, neighborIndexes);

          // Only skip drawing an edge that borders another cell BELONGING
          // TO THE SAME COACH - everything else (a different coach, or no
          // matching neighbour at all, i.e. the true outer edge of this
          // coach's whole area) gets drawn.
          if (neighborI !== null && seeds[neighborI].coachName === coachName) continue;

          borderSegments.push([[p1[1], p1[0]], [p2[1], p2[0]]]);
        }
      });

      if (!fillRings.length) return;

      window.L.polygon(fillRings, {
        stroke: false,
        fillColor: color,
        fillOpacity: 0.28
      })
        .addTo(state.territoryLayer)
        .bindPopup(escapeHtml(label) + "'s assigned area")
        .bindTooltip(escapeHtml(label), { permanent: true, direction: "center", className: "trk-territory-label" });

      borderSegments.forEach(function (segment) {
        window.L.polyline(segment, { color: color, weight: 3, opacity: 0.9 }).addTo(state.territoryLayer);
      });
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
      var color = flagged ? OUT_OF_AREA_COLOR : coachColor(row.coach, row.coach_label);

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
        // flagging it. Keyed by coach docname (not label) so it lines up
        // with state.coachColorByName/state.territories.
        if (row.in_area !== false && row.coach) {
          if (!pointsByCoach[row.coach]) {
            pointsByCoach[row.coach] = { label: row.coach_label || row.coach, points: [] };
          }
          pointsByCoach[row.coach].points.push(point);
        }
      });
    });

    // A coach with an assigned Territory Postcode Areas boundary gets that
    // one drawn instead (plotted below) - this thin coach-coloured hull is
    // only a fallback for coaches nobody has set a territory for yet, where
    // "where their clients happen to be" is all there is to go on.
    var namesWithTerritory = state.territories || {};

    Object.keys(pointsByCoach).forEach(function (coachName) {
      if (namesWithTerritory[coachName]) return;

      var entry = pointsByCoach[coachName];
      if (entry.points.length < 3) return;

      var hull = convexHull(entry.points);
      window.L.polygon(hull, {
        color: coachColor(coachName, entry.label),
        weight: 2,
        fillOpacity: 0.08
      })
        .addTo(state.territoryLayer)
        .bindPopup(escapeHtml(entry.label) + "'s area");
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

  // Native <select><option> elements can't render a colour swatch inside
  // themselves in any browser - there's just no supported way to put a
  // styled element inside an <option>. This legend is the workaround: the
  // same colour used for that coach's pins/area on the map, shown next to
  // their name outside the dropdown instead of unreachably inside it.
  function renderCoachLegend() {
    var legend = el("clientLocationsCoachLegend");
    if (!legend) return;

    var names = Object.keys(state.coachLabelByName).filter(function (name) {
      return !!customCoachColor(name);
    });

    if (!names.length) {
      legend.innerHTML = "";
      return;
    }

    names.sort(function (a, b) {
      return (state.coachLabelByName[a] || "").localeCompare(state.coachLabelByName[b] || "");
    });

    legend.innerHTML = names.map(function (name) {
      return '<span class="trk-coach-legend-item">'
        + '<span class="trk-coach-swatch" style="background:' + escapeHtml(customCoachColor(name)) + ';"></span>'
        + escapeHtml(state.coachLabelByName[name] || name)
        + "</span>";
    }).join("");
  }

  async function loadCoachOptions() {
    var select = el("clientLocationsCoachSelect");

    try {
      var options = await callApi("dashboard.api.shared.coach_logs.get_coach_log_options", {});

      (options || []).forEach(function (opt) {
        state.coachLabelByName[opt.value] = opt.label;
        if (opt.colour) state.coachColorByName[opt.value] = opt.colour;

        if (select) {
          var optionEl = document.createElement("option");
          optionEl.value = opt.value;
          optionEl.textContent = opt.label;
          select.appendChild(optionEl);
        }
      });

      renderCoachLegend();
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
