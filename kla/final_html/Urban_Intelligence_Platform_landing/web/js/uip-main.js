/* Metropolitan Planning Intelligence Platform — main assembly */
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
        /* vertical row-wrap arrows removed — only horizontal arrows are drawn */
        continue;
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

  var DATAV = "3";
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
    // Esri Dark Gray Canvas raster basemap under the vector layers
    var TILE_CACHE = {};
    function baseTile(layer, z, x, y, onImg) {
      var k = layer + "/" + z + "/" + x + "/" + y;
      var e = TILE_CACHE[k];
      if (e) { if (e.img) onImg(e.img); else e.cbs.push(onImg); return; }
      e = TILE_CACHE[k] = { img: null, cbs: [onImg] };
      var im = new Image();
      im.onload = function () {
        var cbs = e.cbs; e.img = im; e.cbs = [];
        cbs.forEach(function (f) { f(im); });
      };
      im.src = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/" + layer +
        "/MapServer/tile/" + z + "/" + y + "/" + x;
    }
    st.base = function (ctx) {
      var s = st.proj.scale(), W = 2 * Math.PI * s;
      var z = Math.max(0, Math.min(16, Math.round(Math.log(W / 256) / Math.LN2)));
      var n = 1 << z, ts = W / n, t = st.proj.translate();
      var x0 = Math.max(0, Math.floor((W / 2 - t[0]) / ts)), x1 = Math.min(n - 1, Math.floor((st.w - t[0] + W / 2) / ts));
      var y0 = Math.max(0, Math.floor((W / 2 - t[1]) / ts)), y1 = Math.min(n - 1, Math.floor((st.h - t[1] + W / 2) / ts));
      ["World_Dark_Gray_Base", "World_Dark_Gray_Reference"].forEach(function (layer) {
        for (var ty = y0; ty <= y1; ty++) {
          for (var tx = x0; tx <= x1; tx++) {
            (function (layer, z, x, y, px, py, size) {
              baseTile(layer, z, x, y, function (img) {
                ctx.drawImage(img, px, py, size + .6, size + .6);
                if (!st._redrawQueued) {
                  st._redrawQueued = true;
                  requestAnimationFrame(function () { st._redrawQueued = false; st.size(); });
                }
              });
            })(layer, z, tx, ty, t[0] - W / 2 + tx * ts, t[1] - W / 2 + ty * ts, ts);
          }
        }
      });
    };
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
      fpVideo.pause();
      fpVideo.src = v.src;
      fpVideo.poster = v.poster || "";
      fp.querySelector(".tag").textContent = v.tag;
      fpVideo.oncanplay = function () {
        fpVideo.oncanplay = null;
        fpVideo.play().catch(function () {});
      };
      fpVideo.load();
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

    /* white-outline pictograms (transparent bg), one per pipeline block */
  var PS = 'fill="none" stroke="rgba(232,238,242,.92)" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg"';
  var PICTOS = {
    seg: '<svg viewBox="0 0 24 24" ' + PS + '><rect x="9" y="2" width="6" height="4"/><rect x="2.5" y="2.5" width="4.5" height="3"/><rect x="17" y="2.5" width="4.5" height="3"/><path d="M12 6v3"/><path d="M2.5 21l3.5-4.5L9.5 21M9 21l3.5-4.5L16 21M15.5 21l3.5-4.5L22.5 21"/></svg>',
    match: '<svg viewBox="0 0 24 24" ' + PS + '><rect x="3.5" y="3.5" width="11" height="11"/><rect x="9.5" y="9.5" width="11" height="11" stroke-dasharray="2.5 2"/></svg>',
    social: '<svg viewBox="0 0 24 24" ' + PS + '><path d="M8 7.5a6 6 0 0 1 8 0"/><path d="M5.2 4.6a10 10 0 0 1 13.6 0"/><path d="M12 10.5c-2.5 0-4.5 2-4.5 4.5 0 3.3 4.5 8 4.5 8s4.5-4.7 4.5-8c0-2.5-2-4.5-4.5-4.5z"/><circle cx="12" cy="15" r="1.6"/></svg>',
    rank: '<svg viewBox="0 0 24 24" ' + PS + '><rect x="3" y="4" width="4" height="16"/><rect x="10" y="9" width="4" height="11"/><rect x="17" y="14" width="4" height="6"/></svg>',
    priority: '<svg viewBox="0 0 24 24" ' + PS + '><path d="M3.5 4h17l-6.5 7.5v5.5l-4 2.5v-8z"/></svg>',
    participate: '<svg viewBox="0 0 24 24" ' + PS + '><rect x="9" y="1.5" width="11" height="6" rx="1.2"/><path d="M12.5 7.5l-1.5 2.5"/><circle cx="6" cy="13" r="2"/><circle cx="12" cy="12.5" r="2"/><circle cx="18" cy="13" r="2"/><path d="M2.5 20a3.5 3.5 0 0 1 7 0M8.5 20a3.5 3.5 0 0 1 7 0M14.5 20a3.5 3.5 0 0 1 7 0"/></svg>',
    toolkits: '<svg viewBox="0 0 24 24" ' + PS + '><path d="M9 8a3 3 0 0 1 6 0"/><rect x="3" y="8" width="18" height="12" rx="1"/><rect x="5.5" y="10.5" width="3.4" height="3.4"/><rect x="10.3" y="10.5" width="3.4" height="3.4"/><rect x="15.1" y="10.5" width="3.4" height="3.4"/><rect x="5.5" y="15.3" width="3.4" height="3.4"/><rect x="10.3" y="15.3" width="3.4" height="3.4"/><rect x="15.1" y="15.3" width="3.4" height="3.4"/></svg>',
    design: '<svg viewBox="0 0 24 24" ' + PS + '><circle cx="12" cy="4" r="1.7"/><path d="M12 5.7L6 20M12 5.7L18 20M8.7 12h6.6M16.6 17.6l2.4 2.4"/></svg>',
    program: '<svg viewBox="0 0 24 24" ' + PS + '><circle cx="12" cy="12" r="4.6"/><path d="M12 3.2v2.6M12 18.2v2.6M3.2 12h2.6M18.2 12h2.6M5.8 5.8l1.8 1.8M16.4 16.4l1.8 1.8M18.2 5.8l-1.8 1.8M7.6 16.4l-1.8 1.8"/></svg>',
    assess: '<svg viewBox="0 0 24 24" ' + PS + '><path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 3.2v3.8h-3.8"/><path d="M4.5 12a7.5 7.5 0 1 1 2.2 5.3" opacity=".45"/><path d="M4.5 20.8V17h3.8" opacity=".45"/></svg>'
  };
  var PSIZE = { seg: 28, match: 24, social: 26, rank: 22, priority: 24, participate: 28, toolkits: 26, design: 28, program: 24, assess: 26 };
  function buildPipeline() {
    var grid = document.getElementById("pipegrid");
    U.PIPE.forEach(function (blk) {
      var d = document.createElement("div");
      d.className = "pnode " + (blk.kind === "src" ? "src" : blk.kind === "out" ? "out" : blk.kind === "feed" ? "feed" : "tool");
      var picto = PICTOS[blk.id] ? '<span class="picto" style="width:' + PSIZE[blk.id] + 'px;height:' + PSIZE[blk.id] + 'px">' + PICTOS[blk.id] + "</span>" : "";
      d.innerHTML = '<span class="no">' + blk.no + '</span>' + picto +
        '<div class="tt">' + (blk.kind === "feed" ? "assessment" : blk.kind === "out" ? "output" : "tool") + '</div>' +
        '<h3>' + blk.title + '</h3><p>' + blk.brief + '</p><canvas></canvas>';
      /* hover panel + canvas anim are pointer-device features; on touch a tap just scrolls to the section */
      var HOVEROK = window.matchMedia("(hover:hover) and (pointer:fine)").matches;
      d.addEventListener("mouseenter", function () {
        d.classList.add("on");
        startAnim(d, blk.id);
        if (!HOVEROK) return;
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

  /* ---------------- 01 segmentation map (embedded slum.html) ---------------- */
  function buildSeg(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML = '<div class="embedbox" id="segmap"><iframe src="/slum.html?embed=1" title="NHA low-income communities map (slum.html)" loading="lazy"></iframe></div>' +
      '<div class="hint">full NHA slum map — communities, plan zones, red / pink AI roofs, congestion blobs (slum.html)</div>';
    body.appendChild(wrap);
  }

  /* ---------------- 02 matching map (embedded checkcadaster.html) ---------------- */
  function buildMatch(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML = '<div class="embedbox" id="mtmap"><iframe src="/checkcadaster.html?embed=1" title="Formal matching — irregular houses vs cadastre buildings" loading="lazy"></iframe></div>' +
      '<div class="hint">check-cadastre map — red irregular houses vs cadastre footprints · orange = potentially irregular buildings (checkcadaster.html)</div>';
    body.appendChild(wrap);
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
    DATA.domMax = max;
  }

  /* ---------------- 03 social map + ranking ---------------- */
  function buildSocial(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML =
      '<div class="embedbox" id="somap"><iframe src="/04_output/social_patterns/bangkok/category_intensity_map.html" title="Neighborhood category intensity map (category_intensity_map.html)" loading="lazy"></iframe></div>' +
      '<div class="hint">neighborhood category intensity — event volumes per community category (category_intensity_map.html)</div>';
    body.appendChild(wrap);
  }

  /* ---------------- 04 ranked irregular neighborhoods ---------------- */
  function buildRank(body) {
    var rk = document.createElement("div");
    rk.className = "reveal";
    rk.innerHTML =
      '<div class="embedbox" id="rkmap"><iframe src="/04_output/social_patterns/bangkok/rankings_map.html" title="Ranked communities — rankings_map.html, rankings only" loading="lazy"></iframe></div>';
    body.appendChild(rk);

    var rkTable = document.createElement("div");
    rkTable.className = "tblwrap";
    rkTable.innerHTML = "<table class='rank'><thead><tr><th>rank</th><th>community</th><th>district</th><th>pop</th></tr></thead><tbody></tbody></table>";
    body.appendChild(rkTable);

    var rkDet = document.createElement("div");
    rkDet.id = "rkdet";
    rkDet.style.display = "none";
    body.appendChild(rkDet);

    var selRow = null;
    var top = DATA.social.features.slice(0, 15);
    var tb = rkTable.querySelector("tbody");
    top.forEach(function (c) {
      var tr = document.createElement("tr");
      tr.innerHTML = "<td class='rk'>#" + c.rank + "</td>" +
        "<td class='nm2'>" + (c.nm || "–") + (c.ne ? " <span class='sep'>/</span> " + c.ne : "") + "</td>" +
        "<td class='nm2'>" + (c.dn || "–") + (c.de ? " <span class='sep'>/</span> " + c.de : "") + "</td>" +
        "<td>" + (c.pop || "–") + "</td>";
      tr.onclick = function () { selectCommunity(c, tr); };

      tb.appendChild(tr);
    });

    function selectCommunity(c, tr) {
      if (selRow) selRow.classList.remove("sel");
      selRow = tr; tr.classList.add("sel");

      /* detail panel: full ranked-element data for the clicked neighborhood */
      var doms = U.DOMAINS.map(function (d) {
        var v = c[d.id] || 0;
        var w = Math.round(v / (DATA.domMax[d.id] || 1) * 120);
        return "<div class='drow'><span>" + d.name + "</span><b>" + v + "</b>" +
          "<i class='bar' style='width:" + w + "px;background:linear-gradient(90deg," + d.color + "," + d.color + ")'></i></div>";
      }).join("");
      rkDet.innerHTML =
        "<div class='k'><span class='label'>selected neighborhood</span><span class='label'>rank #" + c.rank + " · score " + c.score + "/100</span></div>" +
        "<h3>" + (c.nm || "–") + (c.ne ? " <span class='en'>" + c.ne + "</span>" : "") + "</h3>" +
        "<p class='meta'>" + (c.dn || "–") + (c.de ? " district · " + c.de : "") + " · population " + (c.pop || "–") +
        " · " + c.tot + " events · " + c.nd + " documents</p>" +
        "<div class='doms'>" + doms + "</div>";
      rkDet.style.display = "block";

      /* zoom the embedded rankings map to the neighborhood extents */
      var fr = document.querySelector("#rkmap iframe");
      if (fr && c.bb) fr.contentWindow.postMessage({ type: "uipZoom", bb: c.bb }, "*");
      document.getElementById("rkmap").scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  /* ---------------- 05 priorities ---------------- */
  function buildPriority(body) {
    var wrap = document.createElement("div");
    wrap.className = "reveal";
    wrap.innerHTML =
      '<div class="embedbox" id="prmap"><iframe src="/04_output/social_patterns/bangkok/prioritiesmap.html" title="Combined priorities — prioritiesmap.html, mean of the four rankings" loading="lazy"></iframe></div>' +
      '<div class="hint">combined priority = mean of the four rankings (deprivation · danger · flood · build-code) — hover a pin for the pulse rings, click a pin for the full neighborhood profile and its main problems</div>';
    body.appendChild(wrap);
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
        '<span class="cnt">' + cards.length + " techniques · background: per-technique imagery (Wikimedia Commons)</span></div>" +
        '<div class="caro-wrap"><button class="caro-btn prev">‹</button><div class="caro"></div><button class="caro-btn next">›</button></div>';
      var caro = gr.querySelector(".caro");
      cards.forEach(function (c) {
        var d = document.createElement("div");
        d.className = "pcard";
        var tags = c.tags.map(function (t) {
          var toolkit = /^(METRO POLICY )?TOOLKIT/.test(t), th = t === "TH";
          return '<span class="tag' + (toolkit ? " toolkit" : th ? " th" : "") + '">' + t + "</span>";
        }).join("");
        d.innerHTML = '<div class="bg" style="background-image:url(' + (c.img || cl.img) + ')"></div>' +
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

  /* scroll to a participation technique card by title; flash it */
  function goToTechnique(title) {
    var cards = document.querySelectorAll(".pcard");
    for (var i = 0; i < cards.length; i++) {
      var h = cards[i].querySelector("h4");
      if (h && (h.textContent === title || h.textContent.indexOf(title) > -1)) {
        cards[i].scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
        cards[i].classList.remove("flash");
        void cards[i].offsetWidth; /* restart transition */
        cards[i].classList.add("flash");
        setTimeout((function (c) { return function () { c.classList.remove("flash"); }; })(cards[i]), 2400);
        return;
      }
    }
  }

  /* ---------------- 06 toolkits ---------------- */
  function buildToolkits(body) {
    var snap = document.createElement("div");
    snap.id = "toolkitsnap";
    snap.className = "reveal";
    body.appendChild(snap);
    var detail = document.createElement("div");
    detail.id = "toolkitdetail";
    detail.className = "reveal";
    body.appendChild(detail);
    detail.addEventListener("click", function (e) {
      var el = e.target.closest(".teq-link");
      if (!el) return;
      goToTechnique(el.getAttribute("data-tech"));
    });

    var sel = 0;
    var cards = U.TOOLKITS.map(function (k, i) {
      var d = document.createElement("div");
      d.className = "kpick" + (i === 0 ? " sel" : "");
      d.innerHTML = '<span class="no">METRO POLICY TOOLKIT ' + k.n + "</span>" +
        '<div class="im" style="background-image:url(' + k.img + ')"></div>' +
        '<div class="nm">' + k.name + (k.thai ? '<br><span style="font-size:11px;color:var(--muted)">' + k.thai + "</span>" : "") + "</div>";
      snap.appendChild(d);
      return d;
    });

    function select(i, scroll) {
      sel = i;
      cards.forEach(function (c, j) { c.classList.toggle("sel", j === i); });
      var k = U.TOOLKITS[i];
      detail.innerHTML =
        '<div class="kd-head"><h3><span style="color:var(--cyan)">METRO POLICY TOOLKIT ' + k.n + "</span> · " + k.name + (k.thai ? ' <span style="font-size:13px;color:var(--muted)">' + k.thai + "</span>" : "") + "</h3>" +
        '<span class="label">selected by scroll</span></div>' +
        '<p style="font-size:13.5px;color:#c4ccd1">' + k.prec + "</p>" +
        '<div><h5 style="margin:0 0 6px;font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--amber);text-transform:uppercase">actions</h5><div class="acts">' +
        k.actions.map(function (a) { return '<span class="act">' + a + "</span>"; }).join("") + "</div></div>" +
        '<div><h5 style="margin:0 0 6px;font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--cyan);text-transform:uppercase">participatory techniques · click to locate</h5><div class="acts">' +
        k.teqs.map(function (a) { return '<span class="act teq teq-link" data-tech="' + a + '" title="Show this technique in section 06">' + a + "</span>"; }).join("") + "</div></div>" +
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
    rows.className = "toolkitrows reveal";
    U.TOOLKITS.forEach(function (k) {
      var d = document.createElement("div");
      d.className = "kflip";
      d.innerHTML = '<div class="inner">' +
        '<div class="kface front"><div class="im" style="background-image:url(' + k.img + ')"></div><div class="in">' +
        "<h4>METRO POLICY TOOLKIT " + k.n + " · " + k.name + "</h4>" +
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
    bz.innerHTML = '<div class="bzscroll"><svg></svg></div><span class="hint">metro policy toolkits ⇢ participation techniques (grouped by class) · hover to trace · swipe the scheme sideways on small screens</span>';
    body.appendChild(bz);
    function drawBezier() {
      var svg = bz.querySelector("svg");
      var W = 1000, toolkitX = 200, clsX = 800;
      var headH = 24, lineH = 15, gap = 26;
      /* right column: one group per participation class — header + its technique names below */
      var groups = U.PART_CLASSES.map(function (pc) {
        return { pc: pc, cards: U.PART_CARDS.filter(function (c) { return c.c === pc.n; }) };
      });
      var y = 20;
      groups.forEach(function (grp) {
        grp.y = y; y += headH;
        grp.cardY = {};
        grp.cards.forEach(function (c) { grp.cardY[c.t] = y + lineH / 2; y += lineH; });
        y += gap;
      });
      var H = y + 6;
      svg.setAttribute("viewBox", "0 0 " + W + " " + H);
      var g = d3.select(svg);
      g.selectAll("*").remove();

      /* technique name -> {y, classN} lookup for link endpoints */
      var teqY = {};
      groups.forEach(function (grp) {
        Object.keys(grp.cardY).forEach(function (t) { teqY[t] = { y: grp.cardY[t], c: grp.pc.n }; });
      });

      /* toolkit nodes sit at the mean height of their techniques, min 42px apart */
      U.TOOLKITS.forEach(function (k) {
        var ys = k.teqs.map(function (t) { return teqY[t].y; });
        k._y = ys.reduce(function (a, b) { return a + b; }, 0) / ys.length;
      });
      var ord = U.TOOLKITS.slice().sort(function (a, b) { return a._y - b._y; });
      for (var i = 1; i < ord.length; i++)
        if (ord[i]._y - ord[i - 1]._y < 42) ord[i]._y = ord[i - 1]._y + 42;
      for (var j = ord.length - 1; j >= 0; j--) {
        var maxY = j === ord.length - 1 ? H - 24 : ord[j + 1]._y - 42;
        if (ord[j]._y > maxY) ord[j]._y = maxY;
      }

      /* links: toolkit -> each related technique line (start at fitted box edge) */
      U.TOOLKITS.forEach(function (k) { k._hw = Math.round(k.name.length * 3.3) + 10; });
      var links = g.append("g");
      U.TOOLKITS.forEach(function (k, i) {
        k.teqs.forEach(function (t) {
          var ty = teqY[t];
          links.append("path")
            .attr("d", "M" + (toolkitX + k._hw) + " " + k._y + " C " + (toolkitX + 260) + " " + k._y + ", " + (clsX - 280) + " " + ty.y + ", " + (clsX - 78) + " " + ty.y)
            .attr("stroke", "#3fd2f0")
            .attr("stroke-width", 1.4)
            .attr("fill", "none")
            .attr("opacity", .38)
            .attr("class", "ln k" + i + " c" + ty.c)
            .attr("data-t", t);
        });
      });

      /* toolkit nodes: rect fitted to the name text with margin */
      var kn = g.selectAll("g.toolkit").data(U.TOOLKITS).enter().append("g")
        .attr("transform", function (k) { return "translate(" + toolkitX + "," + k._y + ")"; })
        .style("cursor", "pointer");
      kn.each(function (k, i) {
        var n = d3.select(this);
        var tx = n.append("text").attr("text-anchor", "middle").attr("dy", 4)
          .attr("fill", "#e8eef2").attr("style", "font:600 11px 'IBM Plex Mono',monospace")
          .text(k.name);
        var bb = tx.node().getBBox();
        n.insert("rect", "text")
          .attr("x", bb.x - 8).attr("y", bb.y - 5).attr("width", bb.width + 16).attr("height", bb.height + 10)
          .attr("fill", "#131a1f").attr("stroke", "#3fd2f0");
      });

      /* class group headers: rect fitted to text */
      var hn = g.selectAll("g.grp").data(groups).enter().append("g")
        .attr("transform", function (grp) { return "translate(" + clsX + "," + (grp.y + headH / 2) + ")"; })
        .style("cursor", "pointer");
      hn.each(function (grp) {
        var n = d3.select(this);
        var tx = n.append("text").attr("text-anchor", "middle").attr("dy", 4)
          .attr("fill", grp.pc.color).attr("style", "font:600 10px 'IBM Plex Mono',monospace")
          .text(grp.pc.n + " · " + grp.pc.name.toUpperCase());
        var bb = tx.node().getBBox();
        n.insert("rect", "text")
          .attr("x", bb.x - 7).attr("y", bb.y - 4).attr("width", bb.width + 14).attr("height", bb.height + 8)
          .attr("fill", "#131a1f").attr("stroke", grp.pc.color);
      });

      /* technique names below each group header */
      var tnodes = [];
      groups.forEach(function (grp) {
        grp.cards.forEach(function (c) {
          var tn = g.append("text")
            .attr("class", "teqline")
            .attr("x", clsX - 70).attr("y", grp.cardY[c.t] + 3.5)
            .text(c.t);
          tnodes.push({ el: tn, t: c.t });
        });
      });

      function dim(cls_) {
        links.selectAll("path").attr("opacity", cls_ == null ? .38 : .1);
        if (cls_ != null) links.selectAll("path." + cls_).attr("opacity", 1);
      }
      kn.on("mouseenter", function (evt, k) { dim("k" + (k.n - 1)); })
        .on("mouseleave", function () { dim(null); })
        .on("click", function (evt, k) {
          select(k.n - 1, true);
          snap.scrollIntoView({ behavior: "smooth", block: "center" });
        });
      hn.on("mouseenter", function (evt, grp) { dim("c" + grp.pc.n); })
        .on("mouseleave", function () { dim(null); });
      tnodes.forEach(function (tn) {
        tn.el.on("mouseenter", function () {
          links.selectAll("path").attr("opacity", .1);
          links.selectAll("path").filter(function () { return d3.select(this).attr("data-t") === tn.t; }).attr("opacity", 1);
        }).on("mouseleave", function () { dim(null); })
          .on("click", function () { goToTechnique(tn.t); });
      });
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
      { l: "fire", name: "Fire lane", color: "#ff5a4e", img: "img/toolkits/toolkit2-roofs.jpg",
        desc: "METRO POLICY TOOLKIT 2 action: a 6 m fire lane cut through the densest fabric, voted by residents (works notice + layout vote). Connects the two existing temple accesses; drainage and water points run along it.",
        geom: { type: "LineString", coordinates: [[c0[0] - d, c0[1] + d * .7], [c0[0] - d * .3, c0[1] + d * .1], [c0[0] + d * .2, c0[1] - d * .2], [c0[0] + d, c0[1] - d * .6]] } },
      { l: "plots", name: "Re-blocked plots", color: "#3fd2f0", img: "img/toolkits/toolkit1-seggoogle.jpg",
        desc: "Re-blocking: plots re-laid around the fire lane so every unit keeps its area and gains road access. Housing stays resident-built; the community committee co-decides the works sequence.",
        geom: { type: "MultiPolygon", coordinates: [[[[c0[0] - d * .9, c0[1] - d * .9], [c0[0] - d * .2, c0[1] - d * .8], [c0[0] - d * .3, c0[1] - d * .3], [c0[0] - d, c0[1] - d * .4]]]] } },
      { l: "common", name: "Common-use area", color: "#2fd5a5", img: "img/toolkits/toolkit6-heat.webp",
        desc: "On vacated land after re-blocking: a common-use area owned by the community cooperative (METRO POLICY TOOLKIT 6 dividend logic) — playground, meeting hall, and the revenue that funds maintenance.",
        geom: { type: "MultiPolygon", coordinates: [[[[c0[0] + d * .3, c0[1] + d * .2], [c0[0] + d, c0[1] + d * .5], [c0[0] + d * .7, c0[1] + d], [c0[0], c0[1] + d * .7]]]] } },
      { l: "market", name: "Market zone", color: "#ffb547", img: "img/toolkits/toolkit5-density.webp",
        desc: "METRO POLICY TOOLKIT 5 action: vending permits + market days along the main road edge. The street-economy signal that ranked this area becomes taxable, serviced activity — vendors co-manage the rules.",
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
        if (st.base) st.base(ctx);
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
    var seg = sectionEl("seg", "01", "Satellite segmentation",
      "All 1,588 registered low-income communities as red dots over plan zones and AI roofs. Hover a dot for households and people; zoom a region — the fabric THEOS-2 measures rooftop by rooftop.",
      "tool · imagery → candidates");
    buildSeg(seg);
    addVid(seg, "seg");
    addVid(seg, "seg2");
    addVid(seg, "seg3");

    var mt = sectionEl("match", "02", "Formal matching",
      "Segmented blocks are checked against the official cadastre and zoning — the first filter layer for irregular neighborhoods.",
      "tool · segmented blocks → irregular neighborhoods");
    buildMatch(mt);
    addVid(mt, "match");

    var so = sectionEl("social", "03", "Social sensing",
      "A datalake updated daily — news, complaints, cameras, traffic — filtered into ten domains, quality-checked, and scored per community.",
      "tool · daily feeds → community scores");
    buildSocial(so);
    addVid(so, "social");

    var rk = sectionEl("rank", "04", "Ranked irregular neighborhoods",
      "Cumulative rank over all sensed communities — signal-weighted (natural disaster .30 · technical disaster .25 · crime .15 · traffic .10 · street retail .10 · begging .10), then joined to the segmentation's irregular blocks. The embedded rankings-only map: pick a ranking, its top 30 light up.",
      "tool · scores → ranked irregular blocks");
    buildRank(rk);
    addVid(rk, "rank");

    var pr = sectionEl("priority", "05", "Priorities & selection of areas",
      "The four rankings combined into one priority score — the mean position across deprivation, dangerous events, flood exposure and build-code risk. The combined top 30 carry the selection weight; hover a pin for the pulse rings, click for the full neighborhood profile and its main problems.",
      "tool · ranked → selected areas");
    buildPriority(pr);
    addVid(pr, "priority");

    var pa = sectionEl("participate", "06", "Selection of participation techniques",
      "The card deck behind every intervention: techniques from a 49-case review, grouped by Arnstein/IAP2 class, each group on its own class imagery. Carousels per class; METRO POLICY TOOLKIT tags bind techniques to metro policy toolkits.",
      "tool · techniques per area");
    buildParticipate(pa);

    var ki = sectionEl("toolkits", "07", "Metro policy toolkits",
      "Scroll the picker — the centered metro policy toolkit is selected. Below: all six metro policy toolkits as flip cards (front: precedent and image; back: action list + participatory techniques), and the interactive scheme wiring metro policy toolkits to participation classes.",
      "tool · one metro policy toolkit per intervention");
    buildToolkits(ki);

    var de = sectionEl("design", "08→", "Design & approval of urban intervention",
      "The selected metro policy toolkit becomes a strategy: layers of change on the map of the #1 ranked area, each location connected to a component card that flips to its description. The walkthrough video shows the full journey; approval passes through the participation gate.",
      "tool · metro policy toolkit → approved strategy");
    buildDesign(de);
  }


  /* ---------------- floating mini-pipeline nav ----------------
     Appears once the user first scrolls below the hero pipeline; white blocks,
     the block(s) of the section currently in view turn red. Click jumps to it. */
  function buildPipeNav() {
    var nav = document.createElement("nav");
    nav.id = "pipenav";
    nav.setAttribute("aria-label", "pipeline minimap");
    var nameEl = document.createElement("span");
    nameEl.id = "pipenavname";
    var nodes = U.PIPE.map(function (blk) {
      var b = document.createElement("a");
      b.href = "#sec-" + blk.sec;
      b.innerHTML = "<i>" + blk.no + "</i>" + '<span class="pic">' + PICTOS[blk.id] + "</span>" + '<span class="tip">' + blk.title + "</span>";
      b.addEventListener("click", function (e) {
        e.preventDefault();
        var sec = document.getElementById("sec-" + blk.sec);
        if (!sec) return;
        /* instant jump, then re-aim once lazy iframes above the target finish
           loading and shift the layout (smooth scroll aborts on those shifts) */
        window.scrollTo({ top: sec.getBoundingClientRect().top + window.scrollY - 70, behavior: "instant" });
        setTimeout(function () {
          window.scrollTo({ top: sec.getBoundingClientRect().top + window.scrollY - 70, behavior: "instant" });
        }, 800);
      });
      nav.appendChild(b);
      b.setAttribute("data-name", blk.no + " · " + blk.title);
      return { el: b, sec: blk.sec, blk: blk };
    });
    /* hovered block name shows in a strip below the icons (delegated, event-flake-proof) */
    nav.appendChild(nameEl);
    function nameFromEvent(e) {
      var a = e.target && e.target.closest ? e.target.closest("a") : null;
      nameEl.textContent = a ? a.getAttribute("data-name") : "";
    }
    ["mousemove", "mouseover", "mouseenter"].forEach(function (ev) {
      nav.addEventListener(ev, nameFromEvent);
    });
    nav.addEventListener("mouseleave", function () { nameEl.textContent = ""; });
    /* some pipeline blocks share one section (↺ → social, → → design);
       each block anchors at the section its sec id names */
    document.body.appendChild(nav);

    var shown = false;
    function onScroll() {
      var pipe = document.getElementById("pipe");
      if (!shown && pipe && window.scrollY > pipe.offsetTop + pipe.offsetHeight) {
        shown = true;
        nav.classList.add("on");
      }
      /* block-level current: the red highlight steps block by block
         as each block's own section crosses mid-viewport */
      var curNode = null, bestTop = -Infinity;
      nodes.forEach(function (n) {
        var el = document.getElementById("sec-" + n.blk.sec);
        if (!el) return;
        var t = el.getBoundingClientRect().top;
        if (t <= window.innerHeight * 0.5 && t > bestTop) { bestTop = t; curNode = n; }
      });
      nodes.forEach(function (n) { n.el.classList.toggle("here", n === curNode); });
    }
    /* embedded webviews here do not always deliver window scroll events (same quirk kickMaps works around) */
    ["scroll", "mousewheel", "wheel", "mousemove", "touchstart", "pointerdown", "keydown"].forEach(function (ev) {
      window.addEventListener(ev, onScroll, { passive: true });
    });
    onScroll();
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
    buildPipeNav();
  }).catch(function (e) {
    document.getElementById("sections").innerHTML =
      '<div class="wrap"><p style="color:var(--red);font-family:var(--mono);font-size:12px">data load failed: ' + e + "</p></div>";
  });
})();
