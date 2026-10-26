/* Urban Intelligence Platform — main assembly */
(function () {
  "use strict";
  var U = window.UIP;
  var DATA = {};
  var tooltip = document.getElementById("tooltip");
  var UIP_MAPS = [];
  function kickMaps() {
    UIP_MAPS.forEach(function (m) { m.size(); });
    drawPipeArrows();
  }
  window.addEventListener("resize", drawPipeArrows);

  /* flow arrows between pipeline blocks (same-row: horizontal; row wrap: elbow down to next block) */
  /* pixel-art flow arrows — pixelarticons "arrow-right" (MIT, pixelarticons.com), 24×24 grid.
     Horizontal arrows: icon as-is. Row-wrap arrows: rotated 90° to point down into the next row. */
  var ARROW_PATHS =
    '<path d="M4 11v2h16v-2zm12 2v2h2v-2zm-2 2v2h2v-2zm-2 2v2h2v-2zm4-6V9h2v2z"/>' +
    '<path d="M14 15V7h2v8zm-2 2V5h2v12z"/>';

  function drawPipeArrows() {
    var grid = document.getElementById("pipegrid");
    var svg = document.getElementById("pipearrows");
    if (!grid || !svg || !grid.children.length) return;
    var gr = grid.getBoundingClientRect();
    if (gr.width < 60) return;
    var W = Math.round(gr.width), H = Math.round(gr.height);
    svg.setAttribute("width", W); svg.setAttribute("height", H);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var rects = Array.prototype.map.call(grid.children, function (n) {
      var r = n.getBoundingClientRect();
      return { l: r.left - gr.left, t: r.top - gr.top, r: r.right - gr.left, b: r.bottom - gr.top,
               cx: (r.left + r.right) / 2 - gr.left, cy: (r.top + r.bottom) / 2 - gr.top };
    });
    var S = 24, body = "";
    for (var i = 0; i < rects.length - 1; i++) {
      var a = rects[i], b = rects[i + 1];
      var tx, ty, rot = 0;
      if (Math.abs(a.cy - b.cy) < 20) {
        var gap = b.l - a.r;
        if (gap < S + 6) continue;
        tx = Math.round(a.r + (gap - S) / 2);
        ty = Math.round(a.cy - S / 2);
      } else {
        var vgap = b.t - a.b;
        if (vgap < S + 6) continue;
        rot = 90;
        tx = Math.round(b.cx - S / 2);                // point down into the next row's first block
        ty = Math.round(a.b + (vgap - S) / 2);
      }
      body += '<g transform="translate(' + tx + "," + ty + ")" + (rot ? " rotate(90)" : "") + '">' + ARROW_PATHS + "</g>";
    }
    svg.innerHTML = '<g fill="#a9bec9" shape-rendering="crispEdges">' + body + "</g>";
  }
  ["scroll", "mousewheel", "wheel", "mousemove", "touchstart", "pointerdown", "keydown"].forEach(function (ev) {
    window.addEventListener(ev, kickMaps, { passive: true });
  });

  function showTip(html, x, y) {
    tooltip.innerHTML = html;
    tooltip.style.opacity = 1;
    var w = tooltip.offsetWidth, h = tooltip.offsetHeight;
    tooltip.style.left = Math.min(window.innerWidth - w - 10, x + 14) + "px";
    tooltip.style.top = Math.min(window.innerHeight - h - 10, Math.max(8, y - h - 8)) + "px";
  }
  function hideTip() { tooltip.style.opacity = 0; }

  var DATAV = "2";
  function loadJSON(p) { return fetch(p + (p.indexOf("?") < 0 ? "?" : "&") + "v=" + DATAV).then(function (r) { return r.json(); }); }

  /* ---------------- map factory: canvas under svg ---------------- */
  function makeMap(container, aspectRatio, fitFeats) {
    container.classList.add("mapbox");
    container.style.height = "0";
    container.style.paddingBottom = (aspectRatio * 100) + "%";
    var canvas = document.createElement("canvas");
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    container.appendChild(canvas);
    container.appendChild(svg);
    var st = { el: container, canvas: canvas, svg: svg, proj: null, path: null, w: 0, h: 0, layers: [] };

    function size() {
      var r = container.getBoundingClientRect();
      if (r.width < 40) return;
      var w = Math.round(r.width * (window.devicePixelRatio > 1 ? 1.5 : 1));
      if (st.w && Math.abs(w - st.w) < 2) return;
      st.w = canvas.width = w;
      st.h = canvas.height = Math.round(st.w * aspectRatio);
      svg.setAttribute("viewBox", "0 0 " + st.w + " " + st.h);
      svg.setAttribute("preserveAspectRatio", "none");
      st.proj = d3.geoMercator().fitExtent([[6, 6], [st.w - 6, st.h - 6]], { type: "FeatureCollection", features: fitFeats });
      st.path = d3.geoPath(st.proj);
      st.layers.forEach(function (l) { l.draw(st); });
    }
    st.size = size;
    st.onresize = function (l) { st.layers.push(l); if (st.w) l.draw(st); };
    window.addEventListener("resize", function () { size(); });
    if (window.ResizeObserver) {
      new ResizeObserver(function () { size(); }).observe(container);
    }
    // IAB/webview quirk: layout can start at innerWidth 0, timers can freeze, and no resize event fires.
    // Poll for real browsers, and re-check on any user gesture as a fallback.
    var tries = 0;
    (function poll() {
      size();
      if (st.w || ++tries > 120) return;
      setTimeout(poll, 300);
    })();
    UIP_MAPS.push(st);
    return st;
  }

  function projRing(proj, ring) {
    var out = [];
    for (var i = 0; i < ring.length; i++) {
      var p = proj(ring[i]);
      out.push(p[0], p[1]);
    }
    return out;
  }
  function tracePoly(g, ctx, proj) {
    var polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    for (var i = 0; i < polys.length; i++) {
      var rings = polys[i];
      for (var j = 0; j < rings.length; j++) {
        var pts = projRing(proj, rings[j]);
        ctx.beginPath();
        ctx.moveTo(pts[0], pts[1]);
        for (var k = 2; k < pts.length; k += 2) ctx.lineTo(pts[k], pts[k + 1]);
        ctx.closePath();
        if (j === 0) ctx.fill();
        ctx.stroke();
      }
    }
  }
  function centroidOf(g) {
    var ring = (g.type === "Polygon" ? g.coordinates[0] : g.coordinates[0][0]);
    var x = 0, y = 0, n = ring.length || 1;
    for (var i = 0; i < ring.length; i++) { x += ring[i][0]; y += ring[i][1]; }
    return [x / n, y / n];
  }

  var CAT_COLORS = {};
  var CAT_PALETTE = ["#2e4a5e", "#3d6b7d", "#4f8f8a", "#5d7a4a", "#7d6b3d", "#8a4a42", "#5e4a7d", "#43576b", "#6b5e43", "#3d7d6b"];
  function catColor(c) {
    if (!CAT_COLORS[c]) CAT_COLORS[c] = CAT_PALETTE[Object.keys(CAT_COLORS).length % CAT_PALETTE.length];
    return CAT_COLORS[c];
  }

  /* BIVARIATE 3×3 palette: x = cumulative score, y = event volume */
  var BIV = [
    ["#345f8c", "#3fa2c7", "#57c3b8"],
    ["#6f7fc9", "#9a7bff", "#c98bd9"],
    ["#c96a4a", "#e08a54", "#ff5a4e"]
  ];

  /* ---------------- hero pipeline ---------------- */
  var rafId = null, animBlock = null, animCanvas = null, animStart = 0;
  function startAnim(node, id) {
    var cv = node.querySelector("canvas");
    var mod = window.UIP_BLOCKS && window.UIP_BLOCKS[id];
    if (!cv || !mod) return;
    animBlock = mod; animCanvas = cv; animStart = performance.now();
    var r = node.getBoundingClientRect();
    var dpr = window.devicePixelRatio > 1 ? 1.5 : 1;
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    if (rafId) cancelAnimationFrame(rafId);
    (function loop() {
      var t = (performance.now() - animStart) / 1000;
      animBlock.draw(animCanvas, animCanvas.width, animCanvas.height, t);
      rafId = requestAnimationFrame(loop);
    })();
  }
  function stopAnim() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null; animBlock = null;
  }

  var fp = document.getElementById("floatpanel");
  var fpVideo = fp.querySelector("video");
  var fpTimer = null;
  function showFloat(node, blk) {
    var v = U.VIDEOS[blk.id];
    fp.querySelector("h4").textContent = blk.title;
    document.getElementById("fp-no").textContent = "block " + blk.no;
    fp.querySelector(".fp-body").textContent = blk.long ? blk.long.split(". ").slice(0, 2).join(". ") + "." : blk.brief;
    var vid = fp.querySelector(".fp-vid");
    if (v) {
      vid.style.display = "block";
      fpVideo.src = v.src;
      fpVideo.poster = v.poster || "";
      fp.querySelector(".tag").textContent = v.tag;
      fpVideo.play().catch(function () {});
    } else {
      vid.style.display = "none";
      fpVideo.pause();
    }
    fp.classList.add("on");
    var r = node.getBoundingClientRect();
    var top = r.bottom + 8;
    if (top + 340 > window.innerHeight) top = Math.max(8, r.top - 350);
    fp.style.top = top + "px";
    fp.style.left = Math.max(8, Math.min(window.innerWidth - 420, r.left)) + "px";
  }
  function hideFloat() {
    fp.classList.remove("on");
    fpVideo.pause();
  }

  function buildPipeline() {
    var grid = document.getElementById("pipegrid");
    U.PIPE.forEach(function (blk) {
      var d = document.createElement("div");
      d.className = "pnode " + (blk.kind === "src" ? "src" : blk.kind === "out" ? "out" : blk.kind === "feed" ? "feed" : "tool");
      d.innerHTML = '<span class="no">' + blk.no + '</span>' +
        '<div class="tt">' + (blk.kind === "feed" ? "assessment" : blk.kind === "out" ? "output" : "tool") + '</div>' +
        '<h3>' + blk.title + '</h3><p>' + blk.brief + '</p><canvas></canvas>';
      d.addEventListener("mouseenter", function () {
        d.classList.add("on");
        startAnim(d, blk.id);
        clearTimeout(fpTimer);
        fpTimer = setTimeout(function () { showFloat(d, blk); }, 240);
      });
      d.addEventListener("mouseleave", function () {
        d.classList.remove("on");
        stopAnim();
        clearTimeout(fpTimer);
        hideFloat();
      });
      d.addEventListener("click", function () {
        var sec = document.getElementById("sec-" + blk.sec);
        if (sec) sec.scrollIntoView({ behavior: "smooth" });
      });
      grid.appendChild(d);
    });
    var tries = 0;
    (function pollArrows() {
      drawPipeArrows();
      var svg = document.getElementById("pipearrows");
      if ((svg && svg.childNodes.length) || ++tries > 120) return;
      setTimeout(pollArrows, 300);
    })();
  }

  /* ---------------- section scaffolding ---------------- */
  function sectionEl(sec, no, title, lede, briefTag) {
    var s = document.createElement("section");
    s.className = "s"; s.id = "sec-" + sec;
    s.innerHTML =
      '<div class="wrap">' +
        '<div class="s-head reveal">' +
          '<div><div class="k"><span class="label">' + briefTag + '</span><span class="label">block ' + no + '</span></div>' +
          '<h2 class="sec">' + title + '</h2></div>' +
          '<p class="lede">' + lede + '</p>' +
        '</div>' +
        '<div class="proc reveal">' + U.PROC[sec].map(function (st, i) {
          return '<div class="step"><b>' + (i + 1) + " · " + st[0] + "</b><span>" + st[1] + "</span></div>";
        }).join("") + "</div>" +
        '<div class="sec-body"></div>' +
        '<details class="rollup reveal"><summary>Full description & data sources</summary><div class="body">' +
          '<div class="cols"><div><h5>Full description</h5><p>' + U.ROLLUP[sec][0] + '</p></div>' +
          "<div><h5>Data sources</h5><ul>" + U.ROLLUP[sec][1].map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul></div></div>" +
        "</div></details>" +
      "</div>";
    document.getElementById("sections").appendChild(s);
    return s.querySelector(".sec-body");
  }

  function addVid(parent, sec) {
    var v = U.VIDEOS[sec];
    if (!v) return;
    var d = document.createElement("div");
    d.className = "vidbox reveal";
    d.innerHTML = '<video controls muted loop playsinline preload="metadata" ' + (v.poster ? 'poster="' + v.poster + '"' : "") + '><source src="' + v.src + '" type="video/mp4"></video>' +
      '<div class="cap"><span>' + v.tag + "</span><span>" + v.note + "</span></div>";
    parent.appendChild(d);
  }

  /* ---------------- 01 segmentation map ---------------- */
  function buildSeg(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML = '<div class="mapctl" id="segctl"></div><div id="segmap" style="margin-top:0"></div>' +
      '<div class="maplegend" id="segleg"></div><div class="hint">hover a roof · hull blobs = accepted settlement candidates</div>';
    body.appendChild(wrap);
    var ctl = wrap.querySelector("#segctl");
    var mapDiv = wrap.querySelector("#segmap");
    var leg = wrap.querySelector("#segleg");
    leg.innerHTML = "<div><span class='sw' style='background:#3fd2f0'></span>segmented roof</div>" +
      "<div><span class='sw' style='background:#ffb547'></span>accepted blob (hull)</div>" +
      "<div><span class='sw' style='background:#2fd5a5'></span>raster10 · fill5 variants</div>";

    var sites = DATA.roofs.sites;
    var cur = 0, showHulls = true;
    var siteChips = sites.map(function (s, i) {
      var c = document.createElement("span");
      c.className = "chip" + (i === 0 ? " on" : "");
      c.textContent = s.name + " · " + s.n + " roofs";
      c.onclick = function () {
        cur = i;
        siteChips.forEach(function (x, j) { x.classList.toggle("on", j === i); });
        segMap.size();
      };
      ctl.appendChild(c);
      return c;
    });
    var hc = document.createElement("span");
    hc.className = "chip on"; hc.textContent = "blob hulls";
    hc.onclick = function () { showHulls = !showHulls; hc.classList.toggle("on", showHulls); segMap.size(); };
    ctl.appendChild(hc);

    function siteFeats() {
      return sites[cur].features.map(function (f) {
        return { type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: f.g } };
      });
    }
    var segMap = makeMap(mapDiv, 0.62, siteFeats().concat([{ type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: DATA.hulls.features[0].g } }]));

    segMap.onresize({
      name: "roofs",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);
        var feats = sites[cur].features;
        var hot = null;
        ctx.lineWidth = 0.6;
        ctx.strokeStyle = "rgba(63,210,240,.55)";
        ctx.fillStyle = "rgba(63,210,240,.30)";
        for (var i = 0; i < feats.length; i++) {
          var f = feats[i];
          var polys = f.g;
          for (var pi = 0; pi < polys.length; pi++) {
            var rings = polys[pi];
            for (var j = 0; j < rings.length; j++) {
              var ring = rings[j];
              ctx.beginPath();
              for (var k = 0; k < ring.length; k++) {
                var p = st.proj(ring[k]);
                k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]);
              }
              ctx.closePath();
              if (j === 0) ctx.fill();
              ctx.stroke();
            }
          }
        }
        if (showHulls) {
          DATA.hulls.features.forEach(function (hf, hi) {
            var col = hf.m === "hull" ? "255,181,71" : "47,213,165";
            ctx.fillStyle = "rgba(" + col + ",.10)";
            ctx.strokeStyle = "rgba(" + col + ",.85)";
            ctx.lineWidth = 1.4;
            ctx.setLineDash(hf.m === "hull" ? [] : [5, 4]);
            tracePoly({ type: "MultiPolygon", coordinates: hf.g }, ctx, st.proj);
            ctx.setLineDash([]);
          });
        }
        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        // invisible hull hit areas
        if (showHulls) {
          g.selectAll("path.hullhit").data(DATA.hulls.features).enter().append("path")
            .attr("d", function (hf) { return st.path({ type: "MultiPolygon", coordinates: hf.g }); })
            .attr("fill", "transparent")
            .on("mousemove", function (evt, hf) {
              showTip("<b>" + hf.m + "</b> blob · " + (hf.ok ? "ACCEPTED" : "rejected") +
                "<br>buildings " + hf.b + " · density " + hf.dha + "/ha" +
                "<br>size CV " + hf.scv + " · orient conc " + hf.oc +
                "<br>canal med " + hf.cm + " m · canal≤150m " + Math.round(hf.cs * 100) + "%", evt.clientX, evt.clientY);
            })
            .on("mouseleave", hideTip);
        }
        // roof hit-testing via voronoi-ish: sample every 12th roof bounding circle
        var hits = [];
        for (i = 0; i < feats.length; i += 6) {
          var c0 = centroidOf({ type: "MultiPolygon", coordinates: feats[i].g });
          var p0 = st.proj(c0);
          hits.push({ i: i, p: p0 });
        }
        g.selectAll("circle.rhit").data(hits).enter().append("circle")
          .attr("cx", function (d) { return d.p[0]; }).attr("cy", function (d) { return d.p[1]; })
          .attr("r", 9).attr("fill", "transparent")
          .on("mousemove", function (evt, d) {
            var f = feats[d.i];
            showTip("<b>roof</b> · conf " + (f.cf != null ? f.cf.toFixed(2) : "–") +
              "<br>area " + (f.a != null ? Math.round(f.a) : "–") + " m²" +
              "<br>neighbours≤20m " + (f.n != null ? f.n : "–") +
              "<br>nearest " + (f.d != null ? f.d.toFixed(1) : "–") + " m", evt.clientX, evt.clientY);
          })
          .on("mouseleave", hideTip);
      }
    });
  }

  /* ---------------- 02 matching map ---------------- */
  function buildMatch(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML =
      '<div class="mapctl" id="mtctl">' +
        '<span class="chip on" id="mtZones">regular properties</span>' +
        '<span class="chip on" id="mtIrreg">highlight irregular</span>' +
        '<label class="chip">roof ≤ <input id="mtA" type="range" min="40" max="200" value="90" style="width:80px;vertical-align:middle"> <b id="mtAv" style="font-family:var(--mono)">90</b> m²</label>' +
        '<label class="chip">neighbours ≥ <input id="mtN" type="range" min="2" max="14" value="6" style="width:70px;vertical-align:middle"> <b id="mtNv" style="font-family:var(--mono)">6</b></label>' +
      "</div>" +
      '<div id="mtmap"></div>' +
      '<div class="maplegend" id="mtleg"></div><div class="hint">morphology sliders set the irregularity rule · hover roofs and zones</div>';
    body.appendChild(wrap);
    var mapDiv = wrap.querySelector("#mtmap");
    var leg = wrap.querySelector("#mtleg");
    leg.innerHTML = "<div><span class='sw' style='background:#ff5a4e'></span>irregular (outside plan / dense small roofs)</div>" +
      "<div><span class='sw' style='background:#3fd2f0'></span>conforming</div>" +
      "<div><span class='sw' style='background:#4f8f8a'></span>plan zone (regular properties)</div>";

    var site = DATA.roofs.sites[0].features;
    var zones = DATA.zones.features;
    var maxA = 90, minN = 6, showZones = true, hi = true;

    var fit = site.slice(0, 400).map(function (f) { return { type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: f.g } }; });
    var mtMap = makeMap(mapDiv, 0.62, fit);

    function classify(f) {
      var irregular = (f.a != null && f.a <= maxA && f.n != null && f.n >= minN);
      return irregular;
    }

    mtMap.onresize({
      name: "match",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);

        // zone id raster for hit tests
        var off = document.createElement("canvas");
        off.width = st.w; off.height = st.h;
        var octx = off.getContext("2d");
        var idToFeat = [];
        if (showZones) {
          zones.forEach(function (z, zi) {
            octx.fillStyle = "rgb(" + ((zi + 1) >> 8 & 255) + "," + ((zi + 1) & 255) + ",0)";
            octx.strokeStyle = octx.fillStyle;
            tracePoly({ type: "MultiPolygon", coordinates: z.g }, octx, st.proj);
            // visible layer
            var col = catColor(z.c || z.u);
            ctx.fillStyle = col + "55";
            ctx.strokeStyle = col;
            ctx.lineWidth = 0.8;
            ctx.setLineDash([3, 3]);
            tracePoly({ type: "MultiPolygon", coordinates: z.g }, ctx, st.proj);
            ctx.setLineDash([]);
            idToFeat.push(z);
          });
        }
        var px = null;
        try { px = octx.getImageData(0, 0, st.w, st.h).data; } catch (e) { px = null; }

        function zoneAt(p) {
          if (!px) return null;
          var xi = Math.max(0, Math.min(st.w - 1, p[0] | 0)), yi = Math.max(0, Math.min(st.h - 1, p[1] | 0));
          var o = (yi * st.w + xi) * 4;
          var id = (px[o] << 8) + px[o + 1];
          return id > 0 ? idToFeat[id - 1] : null;
        }

        var counts = { ir: 0, reg: 0 };
        var hits = [];
        ctx.lineWidth = 0.6;
        for (var i = 0; i < site.length; i++) {
          var f = site[i];
          var geom = { type: "MultiPolygon", coordinates: f.g };
          var c0 = centroidOf(geom);
          var p0 = st.proj(c0);
          var z = showZones ? zoneAt(p0) : null;
          var irregular = hi ? (classify(f) || !z) : classify(f);
          var col = irregular ? "255,90,78" : "63,210,240";
          irregular ? counts.ir++ : counts.reg++;
          ctx.fillStyle = "rgba(" + col + ",.42)";
          ctx.strokeStyle = "rgba(" + col + ",.8)";
          tracePoly(geom, ctx, st.proj);
          if (i % 5 === 0) hits.push({ i: i, p: p0, z: z });
        }
        wrap.querySelector("#mtIrreg").textContent = "irregular: " + counts.ir + " / " + (counts.ir + counts.reg);

        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        g.selectAll("circle").data(hits).enter().append("circle")
          .attr("cx", function (d) { return d.p[0]; }).attr("cy", function (d) { return d.p[1]; })
          .attr("r", 8).attr("fill", "transparent")
          .on("mousemove", function (evt, d) {
            var f = site[d.i];
            var ir = hi ? (classify(f) || !d.z) : classify(f);
            showTip((ir ? "<b>IRREGULAR</b>" : "<b>conforming</b>") + " roof" +
              "<br>area " + Math.round(f.a || 0) + " m² · neighbours " + f.n +
              "<br>zone: " + (d.z ? (d.z.c + " · " + d.z.u) : "none — outside plan") +
              "<br>evidence: " + (d.z ? (classify(f) ? "dense small-roof fabric in " + d.z.c : "conforming use") : "no regular-property record"), evt.clientX, evt.clientY);
          })
          .on("mouseleave", hideTip);
        // zone hits
        g.selectAll("path.zhit").data(zones).enter().append("path")
          .attr("d", function (z) { return st.path({ type: "MultiPolygon", coordinates: z.g }); })
          .attr("fill", "transparent")
          .on("mousemove", function (evt, z) { showTip("<b>plan zone</b><br>" + z.c + " · " + z.u + "<br>zone code " + z.z, evt.clientX, evt.clientY); })
          .on("mouseleave", hideTip);
      }
    });

    wrap.querySelector("#mtA").oninput = function () { maxA = +this.value; wrap.querySelector("#mtAv").textContent = maxA; mtMap.size(); };
    wrap.querySelector("#mtN").oninput = function () { minN = +this.value; wrap.querySelector("#mtNv").textContent = minN; mtMap.size(); };
    wrap.querySelector("#mtZones").onclick = function () { showZones = !showZones; this.classList.toggle("on", showZones); mtMap.size(); };
    wrap.querySelector("#mtIrreg").onclick = function () { hi = !hi; this.classList.toggle("on", hi); mtMap.size(); };
  }

  /* ---------------- scores ---------------- */
  function computeScores() {
    var f = DATA.social.features;
    var max = { nd_: 1, td_: 1, cr: 1, ti: 1, sr: 1, bh: 1, tot: 1 };
    f.forEach(function (c) { U.DOMAINS.forEach(function (d) { if (c[d.id] > max[d.id]) max[d.id] = c[d.id]; }); if (c.tot > max.tot) max.tot = c.tot; });
    var W = { nd_: .30, td_: .25, cr: .15, ti: .10, sr: .10, bh: .10 };
    f.forEach(function (c) {
      var s = 0;
      U.DOMAINS.forEach(function (d) { s += W[d.id] * (c[d.id] || 0) / max[d.id]; });
      c.score = Math.round(s * 100);
      c.norm = c.tot / max.tot;
    });
    f.sort(function (a, b) { return b.score - a.score; });
    f.forEach(function (c, i) { c.rank = i + 1; });
    DATA.scoreMax = 100;
    DATA.totMax = max.tot;
  }

  /* ---------------- 03 social map + ranking ---------------- */
  function buildSocial(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML =
      '<div class="mapctl" id="soctl"><span class="chip on" data-d="score">cumulative score</span></div>' +
      '<div id="somap"></div>' +
      '<div class="maplegend" id="soleg"></div><div class="hint">domain layers: toggle a chip · hover a community for its pulse</div>';
    body.appendChild(wrap);
    var ctl = wrap.querySelector("#soctl");
    var mapDiv = wrap.querySelector("#somap");
    var leg = wrap.querySelector("#soleg");

    var curDomain = "score";
    var chips = [];
    function setDomain(d) {
      curDomain = d;
      chips.forEach(function (c) { c.classList.toggle("on", c.dataset.d === d); });
      soMap.size();
    }
    var all = [{ id: "score", name: "cumulative score", color: "score" }].concat(U.DOMAINS);
    all.forEach(function (d) {
      var c = document.createElement("span");
      c.className = "chip"; c.dataset.d = d.id;
      c.textContent = d.name.toLowerCase();
      if (d.color && d.color !== "score") c.innerHTML = '<span class="dot" style="background:' + d.color + '"></span>' + d.name.toLowerCase();
      c.onclick = function () { setDomain(d.id); };
      ctl.appendChild(c);
      chips.push(c);
    });
    chips[0].classList.add("on");

    var feats = DATA.social.features.map(function (c) { return { type: "Feature", geometry: { type: "Point", coordinates: c.c } }; });
    var soMap = makeMap(mapDiv, 0.66, DATA.khet.features.map(function (k) { return { type: "Feature", geometry: { type: "MultiPolygon", coordinates: k.g } }; }));

    function colorOf(c) {
      if (curDomain === "score") {
        var q = c.score / 60;
        return q > .66 ? "#ff5a4e" : q > .33 ? "#ffb547" : "#3fd2f0";
      }
      var d = U.DOMAINS.filter(function (x) { return x.id === curDomain; })[0];
      var v = c[d.id] || 0;
      return v > 2 ? d.color : v > 0 ? d.color + "99" : "#2d3b45";
    }

    soMap.onresize({
      name: "social",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);
        // khet outlines
        ctx.strokeStyle = "rgba(45,59,69,.9)"; ctx.lineWidth = 0.8;
        DATA.khet.features.forEach(function (k) { tracePoly({ type: "MultiPolygon", coordinates: k.g }, ctx, st.proj); });
        // points on svg
        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        var cs = DATA.social.features;
        g.selectAll("circle").data(cs).enter().append("circle")
          .attr("cx", function (c) { return st.proj(c.c)[0]; })
          .attr("cy", function (c) { return st.proj(c.c)[1]; })
          .attr("r", function (c) { return 1.6 + 2.6 * Math.sqrt(c.score / 100); })
          .attr("fill", function (c) { return colorOf(c); })
          .attr("fill-opacity", .78)
          .attr("stroke", "none")
          .style("cursor", "crosshair")
          .on("mousemove", function (evt, c) {
            var rows = U.DOMAINS.map(function (d) {
              return d.name + ": " + (c[d.id] || 0);
            }).join("<br>");
            showTip("<b>" + (c.nm || c.dn || "community") + "</b> · district " + c.dn +
              "<br>rank #" + c.rank + " · score " + c.score + "/100" +
              "<br>pop " + (c.pop || "–") + " · docs " + c.nd +
              "<br><span style='color:#93a3ad'>" + rows + "</span>", evt.clientX, evt.clientY);
          })
          .on("mouseleave", hideTip);
        leg.innerHTML = curDomain === "score"
          ? "<div><span class='sw' style='background:#ff5a4e'></span>score &gt; 40</div><div><span class='sw' style='background:#ffb547'></span>20–40</div><div><span class='sw' style='background:#3fd2f0'></span>&lt; 20</div>"
          : U.DOMAINS.filter(function (d) { return d.id === curDomain; }).map(function (d) {
            return "<div><span class='sw' style='background:" + d.color + "'></span>" + d.name + " intensity</div>";
          }).join("");
      }
    });

    /* ranking sub-block */
    var rk = document.createElement("div");
    rk.className = "reveal";
    rk.style.marginTop = "44px";
    rk.innerHTML =
      '<div class="s-head" style="margin-bottom:18px"><div><div class="k"><span class="label">block 04</span><span class="label">social sensing output</span></div>' +
      "<h2 class='sec' style='font-size:clamp(24px,3.4vw,44px)'>Ranked irregular neighborhoods</h2></div>" +
      "<p class='lede' style='font-size:15px'>Cumulative rank over all sensed communities — signal-weighted (natural disaster .30 · technical disaster .25 · crime .15 · traffic .10 · street retail .10 · begging .10), then joined to the segmentation's irregular blocks. Click a row to locate it; toggle solo / bivariate on the map.</p></div>";

    var mapCtl = document.createElement("div");
    mapCtl.className = "mapctl";
    mapCtl.innerHTML = '<span class="chip on" id="rkSolo">solo score</span><span class="chip" id="rkBiv">bivariate: score × event volume</span>';
    var rkMapDiv = document.createElement("div");
    rkMapDiv.id = "rkmap";
    var rkLeg = document.createElement("div");
    rkLeg.className = "maplegend";
    rk.appendChild(mapCtl); rk.appendChild(rkMapDiv); rk.appendChild(rkLeg);
    var rkTable = document.createElement("div");
    rkTable.className = "tblwrap";
    rkTable.innerHTML = "<table class='rank'><thead><tr><th>rank</th><th>community</th><th>district</th><th>pop</th><th>score</th><th style='width:120px'></th><th>ND</th><th>TD</th><th>CR</th><th>TI</th><th>SR</th><th>BH</th></tr></thead><tbody></tbody></table>";
    rk.appendChild(rkTable);
    body.appendChild(rk);

    var selRow = null;
    var mode = "solo";
    var top = DATA.social.features.slice(0, 15);
    var tb = rkTable.querySelector("tbody");
    top.forEach(function (c) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td class='rk'>#" + c.rank + "</td><td>" + (c.nm || "–") + "</td><td>" + (c.dn || "–") + "</td><td>" + (c.pop || "–") + "</td>" +
        "<td style='color:var(--fg)'>" + c.score + "</td>" +
        "<td><span class='bar' style='width:" + Math.round(c.score * 0.9) + "px'></span></td>" +
        "<td>" + c.nd_ + "</td><td>" + c.td_ + "</td><td>" + c.cr + "</td><td>" + c.ti + "</td><td>" + c.sr + "</td><td>" + c.bh + "</td>";
      tr.onclick = function () {
        if (selRow) selRow.classList.remove("sel");
        selRow = tr; tr.classList.add("sel");
        focusRk(c.c);
      };
      tb.appendChild(tr);
    });

    function bivColor(c) {
      var x = c.score > 40 ? 2 : c.score > 20 ? 1 : 0;
      var y = c.norm > .66 ? 2 : c.norm > .33 ? 1 : 0;
      return BIV[y][x];
    }
    var focusRing = null;
    function focusRk(c) {
      focusRing = c;
      rkMap.size();
      var r = rkMapDiv.getBoundingClientRect();
      window.scrollTo({ top: r.top + window.scrollY - 120, behavior: "smooth" });
    }

    var rkMap = makeMap(rkMapDiv, 0.6, DATA.khet.features.map(function (k) { return { type: "Feature", geometry: { type: "MultiPolygon", coordinates: k.g } }; }));
    rkMap.onresize({
      name: "rank",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);
        ctx.strokeStyle = "rgba(45,59,69,.9)"; ctx.lineWidth = 0.8;
        DATA.khet.features.forEach(function (k) { tracePoly({ type: "MultiPolygon", coordinates: k.g }, ctx, st.proj); });
        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        var cs = DATA.social.features;
        g.selectAll("circle").data(cs).enter().append("circle")
          .attr("cx", function (c) { return st.proj(c.c)[0]; })
          .attr("cy", function (c) { return st.proj(c.c)[1]; })
          .attr("r", function (c) { return 1.5 + (mode === "solo" ? 2.6 * Math.sqrt(c.score / 100) : 3.2 * Math.sqrt(c.norm)); })
          .attr("fill", function (c) { return mode === "solo" ? (c.score > 40 ? "#ff5a4e" : c.score > 20 ? "#ffb547" : "#3fd2f0") : bivColor(c); })
          .attr("fill-opacity", .8)
          .on("mousemove", function (evt, c) { showTip("<b>#" + c.rank + " " + (c.nm || c.dn) + "</b><br>score " + c.score + " · events " + c.tot, evt.clientX, evt.clientY); })
          .on("mouseleave", hideTip);
        if (focusRing) {
          g.append("circle")
            .attr("cx", st.proj(focusRing)[0]).attr("cy", st.proj(focusRing)[1])
            .attr("r", 12).attr("fill", "none").attr("stroke", "#e8eef2").attr("stroke-width", 1.4)
            .attr("stroke-dasharray", "3 3");
        }
      }
    });
    mapCtl.querySelector("#rkSolo").onclick = function () { mode = "solo"; this.classList.add("on"); mapCtl.querySelector("#rkBiv").classList.remove("on"); rkLeg.innerHTML = "<div><span class='sw' style='background:#ff5a4e'></span>score &gt; 40</div><div><span class='sw' style='background:#ffb547'></span>20–40</div><div><span class='sw' style='background:#3fd2f0'></span>&lt; 20</div>"; rkMap.size(); };
    mapCtl.querySelector("#rkBiv").onclick = function () { mode = "biv"; this.classList.add("on"); mapCtl.querySelector("#rkSolo").classList.remove("on");
      var h = "<div style='display:flex;gap:8px;align-items:center'><span style='width:44px'>volume ↑</span><span class='bilegend'>";
      for (var y = 2; y >= 0; y--) for (var x = 0; x < 3; x++) h += "<i style='background:" + BIV[y][x] + "'></i>";
      h += "</span></div><div><span style='margin-left:52px'>score →</span></div>";
      rkLeg.innerHTML = h; rkMap.size(); };
    mapCtl.querySelector("#rkSolo").click();
  }

  /* ---------------- 04 priorities ---------------- */
  function buildPriority(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML = '<div class="mapctl" id="prctl"></div><div id="prmap"></div><div class="maplegend" id="prleg"></div><div class="hint">P1 = act now · P2 = program · P3 = monitor · P4 = watch — hover a district</div>';
    body.appendChild(wrap);

    // aggregate community scores per khet via raster hit test
    var prMap = makeMap(wrap.querySelector("#prmap"), 0.62, DATA.khet.features.map(function (k) { return { type: "Feature", geometry: { type: "MultiPolygon", coordinates: k.g } }; }));
    var PRIO = [
      { name: "P1 · act now", color: "#ff5a4e" },
      { name: "P2 · program", color: "#ffb547" },
      { name: "P3 · monitor", color: "#3fd2f0" },
      { name: "P4 · watch", color: "#2fd5a5" }
    ];

    var khAgg = DATA.khet.features.map(function (k) { return { n: k.n, g: k.g, sum: 0, cnt: 0, top: [] }; });

    prMap.onresize({
      name: "priority",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);

        // id raster for khet assignment
        var off = document.createElement("canvas");
        off.width = Math.max(2, st.w >> 1); off.height = Math.max(2, st.h >> 1);
        var octx = off.getContext("2d");
        khAgg.forEach(function (k, ki) {
          k.sum = 0; k.cnt = 0; k.top = [];
          octx.fillStyle = "rgb(" + ((ki + 1) >> 8 & 255) + "," + ((ki + 1) & 255) + ",0)";
          octx.strokeStyle = octx.fillStyle;
          tracePoly({ type: "MultiPolygon", coordinates: k.g }, octx, function (c) {
            var p = st.proj(c); return [p[0] / 2, p[1] / 2];
          });
        });
        var px;
        try { px = octx.getImageData(0, 0, off.width, off.height).data; } catch (e) { px = null; }
        if (px) {
          DATA.social.features.forEach(function (c) {
            var p = st.proj(c.c);
            var xi = Math.max(0, Math.min(off.width - 1, (p[0] / 2) | 0)), yi = Math.max(0, Math.min(off.height - 1, (p[1] / 2) | 0));
            var o = (yi * off.width + xi) * 4;
            var id = (px[o] << 8) + px[o + 1];
            if (id > 0 && id <= khAgg.length) {
              var k = khAgg[id - 1];
              k.sum += c.score; k.cnt++;
              if (k.top.length < 3 && c.score > 15) k.top.push(c);
            }
          });
        }
        // classify quantiles by mean
        var means = khAgg.filter(function (k) { return k.cnt > 0; }).map(function (k) { return k.sum / k.cnt; }).sort(d3.ascending);
        function q(v) {
          if (v >= d3.quantile(means, .875)) return 0;
          if (v >= d3.quantile(means, .625)) return 1;
          if (v >= d3.quantile(means, .375)) return 2;
          return 3;
        }
        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        khAgg.forEach(function (k, ki) {
          if (!k.cnt) return;
          var cls = q(k.sum / k.cnt);
          ctx.fillStyle = PRIO[cls].color + "44";
          ctx.strokeStyle = PRIO[cls].color;
          ctx.lineWidth = 1;
          tracePoly({ type: "MultiPolygon", coordinates: k.g }, ctx, st.proj);
          g.append("path")
            .attr("d", st.path({ type: "MultiPolygon", coordinates: k.g }))
            .attr("fill", "transparent")
            .style("cursor", "crosshair")
            .on("mousemove", function (evt) {
              var topTxt = k.top.length ? k.top.map(function (c) { return "#" + c.rank + " " + (c.nm || c.dn) + " (" + c.score + ")"; }).join("<br>") : "—";
              showTip("<b>" + k.n + "</b> · " + PRIO[cls].name +
                "<br>communities sensed: " + k.cnt +
                "<br>mean score " + Math.round(k.sum / k.cnt) +
                "<br>top irregular:<br><span style='color:#93a3ad'>" + topTxt + "</span>", evt.clientX, evt.clientY);
            })
            .on("mouseleave", hideTip);
        });
      }
    });
    wrap.querySelector("#prleg").innerHTML = PRIO.map(function (p) {
      return "<div><span class='sw' style='background:" + p.color + "'></span>" + p.name + "</div>";
    }).join("");
  }

  /* ---------------- 05 participation ---------------- */
  function buildParticipate(body) {
    U.PART_CLASSES.forEach(function (cl) {
      var cards = U.PART_CARDS.filter(function (c) { return c.c === cl.n; });
      var gr = document.createElement("div");
      gr.className = "pgroup g" + cl.n + " reveal";
      var clsName = cl.n === 3 ? "Involve / co-produce" : cl.n === 4 ? "Collaborate / co-decide" : cl.name;
      gr.innerHTML =
        '<div class="ghead"><h3><span style="color:' + cl.color + '">class ' + cl.n + "</span> · " + clsName + "</h3>" +
        '<span class="cnt">' + cards.length + " techniques · background: class imagery</span></div>" +
        '<div class="caro-wrap"><button class="caro-btn prev">‹</button><div class="caro"></div><button class="caro-btn next">›</button></div>';
      var caro = gr.querySelector(".caro");
      cards.forEach(function (c) {
        var d = document.createElement("div");
        d.className = "pcard";
        var tags = c.tags.map(function (t) {
          var kit = /^KIT/.test(t), th = t === "TH";
          return '<span class="tag' + (kit ? " kit" : th ? " th" : "") + '">' + t + "</span>";
        }).join("");
        d.innerHTML = '<div class="bg" style="background-image:url(' + cl.img + ')"></div>' +
          '<div class="in"><div style="display:flex;gap:8px;align-items:center"><span class="lvl">' + cl.n + '</span><span class="cls">' + clsName + "</span></div>" +
          "<h4>" + c.t + "</h4><p>" + c.d + '</p><div class="meta">' + tags + "</div></div>";
        caro.appendChild(d);
      });
      gr.querySelector(".prev").onclick = function () { caro.scrollBy({ left: -caro.clientWidth * .8, behavior: "smooth" }); };
      gr.querySelector(".next").onclick = function () { caro.scrollBy({ left: caro.clientWidth * .8, behavior: "smooth" }); };
      body.appendChild(gr);
    });
    var note = document.createElement("p");
    note.className = "reveal";
    note.style.cssText = "margin-top:22px;font-size:13px;color:var(--muted);max-width:80ch";
    note.innerHTML = "<b style='color:var(--fg)'>Design rule:</b> classes 3–5 are the operable pool; classes 1–2 are recorded as context; class 6 is monitored as a leading indicator that classes 1–2 failed. Failure modes tracked: voice without empowerment, participation cut mid-programme, token timing, elite capture, expectation debt.";
    body.appendChild(note);
  }

  /* ---------------- 06 kits ---------------- */
  function buildKits(body) {
    var snap = document.createElement("div");
    snap.id = "kitsnap";
    snap.className = "reveal";
    body.appendChild(snap);
    var detail = document.createElement("div");
    detail.id = "kitdetail";
    detail.className = "reveal";
    body.appendChild(detail);

    var sel = 0;
    var cards = U.KITS.map(function (k, i) {
      var d = document.createElement("div");
      d.className = "kpick" + (i === 0 ? " sel" : "");
      d.innerHTML = '<span class="no">KIT ' + k.n + "</span>" +
        '<div class="im" style="background-image:url(' + k.img + ')"></div>' +
        '<div class="nm">' + k.name + (k.thai ? '<br><span style="font-size:11px;color:var(--muted)">' + k.thai + "</span>" : "") + "</div>";
      snap.appendChild(d);
      return d;
    });

    function select(i, scroll) {
      sel = i;
      cards.forEach(function (c, j) { c.classList.toggle("sel", j === i); });
      var k = U.KITS[i];
      detail.innerHTML =
        '<div class="kd-head"><h3><span style="color:var(--cyan)">KIT ' + k.n + "</span> · " + k.name + (k.thai ? ' <span style="font-size:13px;color:var(--muted)">' + k.thai + "</span>" : "") + "</h3>" +
        '<span class="label">selected by scroll</span></div>' +
        '<p style="font-size:13.5px;color:#c4ccd1">' + k.prec + "</p>" +
        '<div><h5 style="margin:0 0 6px;font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--amber);text-transform:uppercase">actions</h5><div class="acts">' +
        k.actions.map(function (a) { return '<span class="act">' + a + "</span>"; }).join("") + "</div></div>" +
        '<div><h5 style="margin:0 0 6px;font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--cyan);text-transform:uppercase">participatory techniques</h5><div class="acts">' +
        k.teqs.map(function (a) { return '<span class="act teq">' + a + "</span>"; }).join("") + "</div></div>" +
        '<p class="label" style="color:var(--muted)">trigger · ' + k.trigger + "</p>" +
        '<p class="label">participation floor class ' + k.tmin + " → ceiling class " + k.tmax + "</p>";
      if (scroll) {
        var r = cards[i].getBoundingClientRect();
        var mid = r.left + r.width / 2 - window.innerWidth / 2;
        snap.scrollBy({ left: mid, behavior: "smooth" });
      }
    }
    cards.forEach(function (c, i) { c.onclick = function () { select(i, true); }; });
    select(0, false);

    var snapT = null;
    snap.addEventListener("scroll", function () {
      clearTimeout(snapT);
      snapT = setTimeout(function () {
        var mid = null, best = 1e9, bx = 0;
        cards.forEach(function (c, i) {
          var r = c.getBoundingClientRect();
          var m = r.left + r.width / 2;
          var d = Math.abs(m - window.innerWidth / 2);
          if (d < best) { best = d; bx = i; }
        });
        if (bx !== sel) select(bx, false);
      }, 90);
    });

    /* flip card rows */
    var rows = document.createElement("div");
    rows.className = "kitrows reveal";
    U.KITS.forEach(function (k) {
      var d = document.createElement("div");
      d.className = "kflip";
      d.innerHTML = '<div class="inner">' +
        '<div class="kface front"><div class="im" style="background-image:url(' + k.img + ')"></div><div class="in">' +
        "<h4>KIT " + k.n + " · " + k.name + "</h4>" +
        '<p class="prec">' + k.prec + '</p><span class="fliphint">hover / tap to flip → actions & techniques</span></div></div>' +
        '<div class="kface back"><h5>actions</h5><ul>' + k.actions.map(function (a) { return "<li>" + a + "</li>"; }).join("") + "</ul>" +
        "<h5>participatory techniques</h5><div class='teqs'>" + k.teqs.map(function (t) { return "<span class='teq'>" + t + "</span>"; }).join("") + "</div></div>" +
        "</div>";
      d.addEventListener("mouseenter", function () { d.classList.add("flip"); });
      d.addEventListener("mouseleave", function () { d.classList.remove("flip"); });
      d.addEventListener("click", function () { d.classList.toggle("flip"); });
      rows.appendChild(d);
    });
    body.appendChild(rows);

    /* bezier scheme */
    var bz = document.createElement("div");
    bz.id = "bezier";
    bz.className = "reveal";
    bz.innerHTML = '<svg></svg><span class="hint">kits ⇢ participation classes · solid = floor · dashed = ceiling · hover to trace</span>';
    body.appendChild(bz);
    function drawBezier() {
      var svg = bz.querySelector("svg");
      var W = 1000, H = 460;
      svg.setAttribute("viewBox", "0 0 " + W + " " + H);
      var kitX = 190, clsX = 810;
      var kitY = function (i) { return 70 + i * 66; };
      var clsY = function (i) { return 60 + i * 70; };
      var g = d3.select(svg);
      g.selectAll("*").remove();
      var links = g.append("g");
      U.KITS.forEach(function (k, i) {
        [k.tmin, k.tmax].forEach(function (cl, ci) {
          links.append("path")
            .attr("d", "M" + (kitX + 60) + " " + kitY(i) + " C " + (kitX + 260) + " " + kitY(i) + ", " + (clsX - 260) + " " + clsY(cl - 1) + ", " + (clsX - 60) + " " + clsY(cl - 1))
            .attr("stroke", ["#3fd2f0", "#9a7bff"][ci])
            .attr("stroke-width", ci ? 1.4 : 2.2)
            .attr("stroke-dasharray", ci ? "5 5" : "none")
            .attr("fill", "none")
            .attr("opacity", .5)
            .attr("class", "ln k" + i + " c" + cl);
        });
      });
      var kn = g.selectAll("g.kit").data(U.KITS).enter().append("g")
        .attr("transform", function (k, i) { return "translate(" + kitX + "," + kitY(i) + ")"; })
        .style("cursor", "pointer");
      kn.append("rect").attr("x", -60).attr("y", -16).attr("width", 120).attr("height", 32)
        .attr("fill", "#131a1f").attr("stroke", "#3fd2f0");
      kn.append("text").attr("text-anchor", "middle").attr("dy", 4)
        .attr("fill", "#e8eef2").attr("style", "font:600 11px 'IBM Plex Mono',monospace")
        .text(function (k) { return "KIT " + k.n; });
      var cn = g.selectAll("g.cls").data(U.PART_CLASSES).enter().append("g")
        .attr("transform", function (c, i) { return "translate(" + clsX + "," + clsY(i) + ")"; })
        .style("cursor", "pointer");
      cn.append("rect").attr("x", -70).attr("y", -16).attr("width", 140).attr("height", 32)
        .attr("fill", "#131a1f").attr("stroke", function (c) { return c.color; });
      cn.append("text").attr("text-anchor", "middle").attr("dy", 4)
        .attr("fill", function (c) { return c.color; }).attr("style", "font:600 10px 'IBM Plex Mono',monospace")
        .text(function (c) { return c.n + " · " + c.name.split(" ")[0].toUpperCase(); });
      function dim(sel_) {
        links.selectAll("path").attr("opacity", sel_ == null ? .5 : .12);
        if (sel_ != null) links.selectAll("path." + sel_).attr("opacity", 1);
      }
      kn.on("mouseenter", function (evt, k) { dim("k" + (k.n - 1)); })
        .on("mouseleave", function () { dim(null); });
      cn.on("mouseenter", function (evt, c) { dim("c" + c.n); })
        .on("mouseleave", function () { dim(null); });
    }
    drawBezier();
  }

  /* ---------------- 07 design & approval ---------------- */
  function buildDesign(body) {
    addVid(body, "design");

    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.style.marginTop = "18px";
    wrap.innerHTML = '<div class="mapctl"><span class="chip on" data-l="all">all layers</span><span class="chip" data-l="fire">fire lane</span><span class="chip" data-l="plots">re-blocked plots</span><span class="chip" data-l="common">common-use area</span><span class="chip" data-l="market">market zone</span></div>' +
      '<div id="dnmap"></div><div class="hint">illustrative strategy on the #1 ranked irregular area · flip a card for its description</div>';
    body.appendChild(wrap);

    var top = DATA.social.features[0];
    var c0 = top.c;
    var d = 0.004;
    var INTV = [
      { l: "fire", name: "Fire lane", color: "#ff5a4e", img: "img/kits/kit2-roofs.jpg",
        desc: "KIT 2 action: a 6 m fire lane cut through the densest fabric, voted by residents (works notice + layout vote). Connects the two existing temple accesses; drainage and water points run along it.",
        geom: { type: "LineString", coordinates: [[c0[0] - d, c0[1] + d * .7], [c0[0] - d * .3, c0[1] + d * .1], [c0[0] + d * .2, c0[1] - d * .2], [c0[0] + d, c0[1] - d * .6]] } },
      { l: "plots", name: "Re-blocked plots", color: "#3fd2f0", img: "img/kits/kit1-seggoogle.jpg",
        desc: "Re-blocking: plots re-laid around the fire lane so every unit keeps its area and gains road access. Housing stays resident-built; the community committee co-decides the works sequence.",
        geom: { type: "MultiPolygon", coordinates: [[[[c0[0] - d * .9, c0[1] - d * .9], [c0[0] - d * .2, c0[1] - d * .8], [c0[0] - d * .3, c0[1] - d * .3], [c0[0] - d, c0[1] - d * .4]]]] } },
      { l: "common", name: "Common-use area", color: "#2fd5a5", img: "img/kits/kit6-heat.webp",
        desc: "On vacated land after re-blocking: a common-use area owned by the community cooperative (KIT 6 dividend logic) — playground, meeting hall, and the revenue that funds maintenance.",
        geom: { type: "MultiPolygon", coordinates: [[[[c0[0] + d * .3, c0[1] + d * .2], [c0[0] + d, c0[1] + d * .5], [c0[0] + d * .7, c0[1] + d], [c0[0], c0[1] + d * .7]]]] } },
      { l: "market", name: "Market zone", color: "#ffb547", img: "img/kits/kit5-density.webp",
        desc: "KIT 5 action: vending permits + market days along the main road edge. The street-economy signal that ranked this area becomes taxable, serviced activity — vendors co-manage the rules.",
        geom: { type: "MultiPolygon", coordinates: [[[[c0[0] - d, c0[1]], [c0[0] - d * .4, c0[1] - d * .3], [c0[0] + d * .1, c0[1] + d * .1], [c0[0] - d * .5, c0[1] + d * .4]]]] } },
    ];
    var curLayer = "all";

    var fitFeats = [{ type: "Feature", geometry: { type: "Point", coordinates: c0 } }];
    fitFeats.push({ type: "Feature", geometry: INTV[1].geom });
    var dnMap = makeMap(wrap.querySelector("#dnmap"), 0.66, [
      { type: "Feature", geometry: { type: "MultiPolygon", coordinates: [[[[c0[0] - d * 2.2, c0[1] - d * 1.4], [c0[0] + d * 2.2, c0[1] - d * 1.4], [c0[0] + d * 2.2, c0[1] + d * 1.4], [c0[0] - d * 2.2, c0[1] + d * 1.4]]]] } }
    ]);

    var cardEls = [];
    dnMap.onresize({
      name: "design",
      draw: function (st) {
        var ctx = st.canvas.getContext("2d");
        ctx.clearRect(0, 0, st.w, st.h);
        ctx.fillStyle = "#0d1216"; ctx.fillRect(0, 0, st.w, st.h);
        // zones faded
        ctx.globalAlpha = .5;
        DATA.zones.features.forEach(function (z) {
          ctx.fillStyle = catColor(z.c || z.u) + "44";
          ctx.strokeStyle = catColor(z.c || z.u);
          ctx.lineWidth = 0.6;
          tracePoly({ type: "MultiPolygon", coordinates: z.g }, ctx, st.proj);
        });
        ctx.globalAlpha = 1;
        // social points faded
        ctx.fillStyle = "rgba(147,163,173,.5)";
        DATA.social.features.forEach(function (c) {
          var p = st.proj(c.c);
          ctx.fillRect(p[0] - 1, p[1] - 1, 2, 2);
        });
        // intervention layers
        INTV.forEach(function (iv) {
          if (curLayer !== "all" && curLayer !== iv.l) return;
          ctx.strokeStyle = iv.color;
          ctx.fillStyle = iv.color + "33";
          ctx.lineWidth = 2;
          if (iv.geom.type === "LineString") {
            ctx.beginPath();
            iv.geom.coordinates.forEach(function (pt, i) {
              var p = st.proj(pt);
              i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]);
            });
            ctx.stroke();
          } else {
            tracePoly(iv.geom, ctx, st.proj);
          }
        });
        st.svg.innerHTML = "";
        var g = d3.select(st.svg).append("g");
        // markers + connector lines to card anchors
        INTV.forEach(function (iv, i) {
          if (curLayer !== "all" && curLayer !== iv.l) return;
          var mid = iv.geom.type === "LineString"
            ? iv.geom.coordinates[Math.floor(iv.geom.coordinates.length / 2)]
            : centroidOf(iv.geom);
          var p = st.proj(mid);
          var corners = [[st.w * .16, st.h * .1], [st.w * .84, st.h * .16], [st.w * .82, st.h * .88], [st.w * .14, st.h * .86]];
          var anchor = corners[i];
          g.append("line")
            .attr("x1", p[0]).attr("y1", p[1]).attr("x2", anchor[0]).attr("y2", anchor[1])
            .attr("stroke", iv.color).attr("stroke-width", 1).attr("stroke-dasharray", "4 4").attr("opacity", .8);
          g.append("circle").attr("cx", p[0]).attr("cy", p[1]).attr("r", 5)
            .attr("fill", iv.color).attr("stroke", "#030507");
        });
      }
    });

    // floating flip cards
    INTV.forEach(function (iv, i) {
      var el = document.createElement("div");
      el.className = "intv-card";
      var pos = [["2%", "6%"], ["auto", "10%"], ["auto", "auto"], ["2%", "auto"]];
      el.style.left = pos[i][0] === "auto" ? "auto" : pos[i][0];
      el.style.right = (pos[i][1] === "auto" && pos[i][0] === "auto") ? "2%" : (i === 1 || i === 2 ? "2%" : "auto");
      el.style.top = pos[i][1] === "auto" ? "auto" : pos[i][1];
      if (pos[i][1] === "auto") el.style.bottom = "6%";
      el.style.borderColor = iv.color;
      el.innerHTML = '<div class="inner">' +
        '<div class="face front"><img src="' + iv.img + '" alt=""><div class="t">' + iv.name + '</div></div>' +
        '<div class="face back">' + iv.desc + "</div></div>";
      el.addEventListener("click", function () { el.classList.toggle("flip"); });
      el.addEventListener("mouseenter", function () { el.classList.add("flip"); });
      el.addEventListener("mouseleave", function () { el.classList.remove("flip"); });
      wrap.querySelector("#dnmap").appendChild(el);
      cardEls.push(el);
    });

    wrap.querySelectorAll(".mapctl .chip").forEach(function (ch) {
      ch.onclick = function () {
        wrap.querySelectorAll(".mapctl .chip").forEach(function (x) { x.classList.remove("on"); });
        ch.classList.add("on");
        curLayer = ch.dataset.l;
        cardEls.forEach(function (el, i) {
          el.style.display = (curLayer === "all" || INTV[i].l === curLayer) ? "block" : "none";
        });
        dnMap.size();
      };
    });
  }

  /* ---------------- sections wiring ---------------- */
  function buildSections() {
    var seg = sectionEl("seg", "01", "Satellite segmentation tool",
      "Quarterly THEOS-2 epochs are segmented rooftop by rooftop; morphology accepts settlement-candidate blobs. Hover roofs and hulls — every polygon carries its evidence.",
      "tool · imagery → candidates");
    buildSeg(seg);
    addVid(seg, "seg");

    var mt = sectionEl("match", "02", "Match to regular properties",
      "Candidates meet the formal city: parcels, comprehensive-plan zones, regulation. Move the sliders — the irregularity rule is live, and every mismatch is flagged with its evidence.",
      "tool · candidates → irregular blocks");
    buildMatch(mt);
    addVid(mt, "match");

    var so = sectionEl("social", "03–04", "Social sensing tool",
      "A datalake updated daily — news, complaints, cameras, traffic — filtered into ten domains, quality-checked, and scored per community. Below: the cumulative ranking of irregular neighborhoods, solo or bivariate.",
      "tool · irregular blocks → ranked");
    buildSocial(so);
    addVid(so, "social");

    var pr = sectionEl("priority", "05", "Priorities & selection of areas",
      "Severity from the ranking, feasibility from land status and capacity: districts take priority classes P1–P4. Selected areas proceed to participation and a governance kit; the rest keep their trend line.",
      "tool · ranked → selected areas");
    buildPriority(pr);
    addVid(pr, "priority");

    var pa = sectionEl("participate", "06", "Selection of participation techniques",
      "The card deck behind every intervention: techniques from a 49-case review, grouped by Arnstein/IAP2 class, each group on its own class imagery. Carousels per class; KIT tags bind techniques to kits.",
      "tool · techniques per area");
    buildParticipate(pa);

    var ki = sectionEl("kits", "07", "Selection of a kit of urban governance",
      "Scroll the picker — the centered kit is selected. Below: all six kits as flip cards (front: precedent and image; back: action list + participatory techniques), and the interactive scheme wiring kits to participation classes.",
      "tool · one kit per intervention");
    buildKits(ki);

    var de = sectionEl("design", "08→", "Design & approval of urban intervention",
      "The selected kit becomes a strategy: layers of change on the map of the #1 ranked area, each location connected to a component card that flips to its description. The walkthrough video shows the full journey; approval passes through the participation gate.",
      "tool · kit → approved strategy");
    buildDesign(de);
  }

  /* ---------------- reveal ---------------- */
  function wireReveal() {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.08 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  }

  /* ---------------- boot ---------------- */
  Promise.all([
    loadJSON("data/uip-roofs.json"), loadJSON("data/uip-hulls.json"), loadJSON("data/uip-zones.json"),
    loadJSON("data/uip-khet.json"), loadJSON("data/uip-social.json")
  ]).then(function (rs) {
    DATA.roofs = rs[0]; DATA.hulls = rs[1]; DATA.zones = rs[2]; DATA.khet = rs[3]; DATA.social = rs[4];
    computeScores();
    buildPipeline();
    buildSections();
    wireReveal();
  }).catch(function (e) {
    document.getElementById("sections").innerHTML =
      '<div class="wrap"><p style="color:var(--red);font-family:var(--mono);font-size:12px">data load failed: ' + e + "</p></div>";
  });
})();
