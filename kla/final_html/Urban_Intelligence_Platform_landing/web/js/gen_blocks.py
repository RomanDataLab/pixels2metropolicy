import pathlib, os
out = pathlib.Path(__file__).parent / "blocks"
out.mkdir(exist_ok=True)

HDR = "/* UIP pipeline block animation — {id} */\n(function(){{\nwindow.UIP_BLOCKS = window.UIP_BLOCKS || {{}};\n"

files = {}

files["seg.js"] = HDR.format(id="seg") + """
UIP_BLOCKS.seg = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var n = 26, pts = [];
  for (var i = 0; i < n; i++) {
    var a = i * 2.39996, rr = Math.min(w, h) * 0.36 * Math.sqrt(i / n);
    pts.push([w * 0.5 + Math.cos(a) * rr * 1.35, h * 0.55 + Math.sin(a) * rr]);
  }
  var blobR = Math.min(w, h) * 0.44 * (0.75 + 0.25 * Math.sin(t * 1.4));
  g.strokeStyle = "rgba(63,210,240,.4)";
  g.beginPath();
  g.ellipse(w * 0.5, h * 0.55, blobR * 1.25, blobR, 0, 0, 7); g.stroke();
  g.fillStyle = "rgba(63,210,240,.06)"; g.fill();
  for (i = 0; i < n; i++) {
    var vis = (t * 6 + i * 0.61) % n < n * 0.98;
    var sz = 3.5 + 2.5 * (0.5 + 0.5 * Math.sin(i * 9.1));
    var al = 0.35 + 0.5 * Math.max(0, Math.sin(t * 2 + i));
    g.fillStyle = "rgba(232,238,242," + (vis ? al : 0.12) + ")";
    g.fillRect(pts[i][0] - sz / 2, pts[i][1] - sz / 2, sz, sz * 0.8);
    if (vis) { g.strokeStyle = "rgba(63,210,240,.5)"; g.strokeRect(pts[i][0] - sz / 2, pts[i][1] - sz / 2, sz, sz * 0.8); }
  }
} };
})();"""

files["match.js"] = HDR.format(id="match") + """
UIP_BLOCKS.match = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cols = 6, rows = 4, cw = w / cols, ch = h / rows;
  g.strokeStyle = "rgba(45,59,69,.8)";
  for (var i = 1; i < cols; i++) { g.beginPath(); g.moveTo(i * cw, 0); g.lineTo(i * cw, h); g.stroke(); }
  for (i = 1; i < rows; i++) { g.beginPath(); g.moveTo(0, i * ch); g.lineTo(w, i * ch); g.stroke(); }
  var blobs = [[1.6, 1.4, 1.1, 0.9], [3.9, 2.3, 0.8, 1.2], [2.4, 3.1, 0.7, 0.7]];
  for (i = 0; i < blobs.length; i++) {
    var b = blobs[i], hit = Math.sin(t * 2.2 + i * 2) > 0.55;
    g.fillStyle = hit ? "rgba(255,90,78,.35)" : "rgba(63,210,240,.22)";
    g.strokeStyle = hit ? "rgba(255,90,78,.9)" : "rgba(63,210,240,.7)";
    g.beginPath();
    g.ellipse(b[0] * cw, b[1] * ch, b[2] * cw * 0.5, b[3] * ch * 0.5, i, 0, 7);
    g.fill(); g.stroke();
    if (hit) {
      g.fillStyle = "rgba(255,90,78,1)"; g.font = "9px IBM Plex Mono, monospace";
      g.fillText("IRREGULAR", b[0] * cw - 24, b[1] * ch - b[3] * ch * 0.5 - 5);
    }
  }
} };
})();"""

files["social.js"] = HDR.format(id="social") + """
UIP_BLOCKS.social = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cols = ["#3fa2ff", "#ffb547", "#9a7bff", "#ff5a4e", "#2fd5a5", "#c9a227"];
  var cx = w * 0.5, cy = h * 0.5;
  for (var i = 0; i < 6; i++) {
    var ang = t * 0.7 + i * Math.PI / 3;
    var rr = Math.min(w, h) * (0.30 + 0.06 * Math.sin(t * 2 + i));
    var x = cx + Math.cos(ang) * rr * 1.3, y = cy + Math.sin(ang) * rr;
    g.strokeStyle = cols[i] + "66";
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(x, y); g.stroke();
    var ph = 0.5 + 0.5 * Math.sin(t * 3 + i * 1.3);
    g.fillStyle = cols[i];
    g.globalAlpha = 0.35 + 0.6 * ph;
    g.beginPath(); g.arc(x, y, 2.5 + ph * 2, 0, 7); g.fill();
    g.globalAlpha = 1;
  }
  g.strokeStyle = "rgba(232,238,242,.8)";
  g.beginPath(); g.arc(cx, cy, 7 + 3 * Math.sin(t * 3), 0, 7); g.stroke();
  g.fillStyle = "rgba(232,238,242,.14)";
  g.beginPath(); g.arc(cx, cy, 7 + 3 * Math.sin(t * 3), 0, 7); g.fill();
} };
})();"""

files["rank.js"] = HDR.format(id="rank") + """
UIP_BLOCKS.rank = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var n = 8, vals = [];
  for (var i = 0; i < n; i++) vals.push({ v: 0.25 + 0.72 * Math.abs(Math.sin(i * 3.7 + 1)), x: i });
  var phase = (t * 0.5) % 2;
  vals.sort(function (a, b) { return b.v - a.v; });
  if (phase < 1) vals.sort(function (a, b) { return a.x - b.x; });
  var bw = w / n;
  for (i = 0; i < n; i++) {
    var cur = vals[i];
    var bh = cur.v * (h - 22);
    var grad = i < 3 ? "255,90,78" : i < 5 ? "255,181,71" : "63,210,240";
    g.fillStyle = "rgba(" + grad + ",.75)";
    g.fillRect(i * bw + 5, h - 12 - bh, bw - 10, bh);
    g.fillStyle = "rgba(147,163,173,.9)"; g.font = "8.5px IBM Plex Mono, monospace";
    g.fillText("#" + (i + 1), i * bw + 9, h - 3);
  }
  g.fillStyle = "rgba(63,210,240,.8)"; g.font = "9px IBM Plex Mono, monospace";
  g.fillText(phase < 1 ? "SORTING..." : "RANKED", 8, 12);
} };
})();"""

files["priority.js"] = HDR.format(id="priority") + """
UIP_BLOCKS.priority = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cols = 7, rows = 4, cw = w / cols, ch = h / rows;
  var P = ["rgba(255,90,78,", "rgba(255,181,71,", "rgba(63,210,240,", "rgba(47,213,165,"];
  for (var i = 0; i < cols; i++) for (var j = 0; j < rows; j++) {
    var k = (i * 7 + j * 13) % 4;
    var ph = (t * 1.2 + (i + j) * 0.22) % 2;
    var fill = ph < 1 ? ph : 1;
    g.fillStyle = P[k] + (0.10 + 0.30 * fill) + ")";
    g.fillRect(i * cw + 3, j * ch + 3, cw - 6, ch - 6);
    g.strokeStyle = P[k] + "0.8)";
    g.strokeRect(i * cw + 3, j * ch + 3, cw - 6, ch - 6);
    if (k === 0 && fill > 0.9) {
      g.fillStyle = "rgba(255,90,78,1)"; g.font = "8px IBM Plex Mono, monospace";
      g.fillText("P1", i * cw + 7, j * ch + 13);
    }
  }
} };
})();"""

files["participate.js"] = HDR.format(id="participate") + """
UIP_BLOCKS.participate = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cols = ["#8a97a3", "#6f9ec4", "#3fd2f0", "#2fd5a5", "#ffb547", "#ff5a4e"];
  var n = 6;
  for (var i = 0; i < n; i++) {
    var ph = (t * 0.9 + i * 0.5) % n;
    var lift = Math.sin(Math.PI * Math.min(ph, 1)) * 14;
    var x = w * 0.5 + (i - (n - 1) / 2) * (w * 0.13);
    var y = h * 0.62 - lift - Math.abs(i - (n - 1) / 2) * 2;
    var cw2 = w * 0.11, ch2 = h * 0.34;
    g.save();
    g.translate(x, y); g.rotate((i - (n - 1) / 2) * 0.06);
    g.fillStyle = "rgba(19,26,31,.95)"; g.fillRect(-cw2 / 2, -ch2 / 2, cw2, ch2);
    g.strokeStyle = cols[i]; g.lineWidth = 1.4;
    g.strokeRect(-cw2 / 2, -ch2 / 2, cw2, ch2);
    g.fillStyle = cols[i]; g.fillRect(-cw2 / 2, -ch2 / 2, cw2, 3);
    g.fillStyle = cols[i]; g.font = "10px IBM Plex Mono, monospace";
    g.fillText(String(i + 1), -cw2 / 2 + 6, -ch2 / 2 + 16);
    g.restore();
  }
} };
})();"""

files["kits.js"] = HDR.format(id="kits") + """
UIP_BLOCKS.kits = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cx = w * 0.5, cy = h * 0.52, cw2 = w * 0.34, ch2 = h * 0.46;
  var ang = t * 1.1;
  var sc = Math.abs(Math.cos(ang));
  g.save(); g.translate(cx, cy);
  g.strokeStyle = "rgba(63,210,240,.85)"; g.lineWidth = 1.4;
  g.strokeRect(-cw2 / 2 * sc, -ch2 / 2, cw2 * sc, ch2);
  g.fillStyle = "rgba(63,210,240,.08)"; g.fillRect(-cw2 / 2 * sc, -ch2 / 2, cw2 * sc, ch2);
  var front = Math.cos(ang) > 0;
  g.textAlign = "center";
  g.fillStyle = front ? "rgba(232,238,242,.95)" : "rgba(255,181,71,.95)";
  g.font = "10px IBM Plex Mono, monospace";
  g.fillText(front ? "KIT" : "ACTIONS", 0, -ch2 / 2 + 18);
  if (!front) {
    g.fillStyle = "rgba(232,238,242,.7)";
    for (var i = 0; i < 4; i++) g.fillRect(-cw2 * 0.32, -ch2 * 0.16 + i * 16, cw2 * 0.64 * (0.6 + 0.3 * Math.sin(i * 7)), 5);
  } else {
    g.fillStyle = "rgba(232,238,242,.55)";
    g.fillRect(-cw2 * 0.3, -ch2 * 0.1, cw2 * 0.6, ch2 * 0.42);
  }
  g.restore(); g.textAlign = "left";
} };
})();"""

files["design.js"] = HDR.format(id="design") + """
UIP_BLOCKS.design = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var ph = (t * 0.55) % 1;
  g.strokeStyle = "rgba(63,210,240,.7)";
  g.beginPath();
  for (var i = 0; i <= 40 * ph; i++) {
    var x = w * 0.08 + (w * 0.84) * (i / 40);
    var y = h * 0.6 + Math.sin(i * 0.5) * h * 0.14;
    i ? g.lineTo(x, y) : g.moveTo(x, y);
  }
  g.stroke();
  g.strokeStyle = "rgba(255,181,71,.8)";
  var sq = Math.min(1, Math.max(0, ph * 1.6 - 0.3));
  g.strokeRect(w * 0.16, h * 0.2, w * 0.2 * sq, h * 0.3 * sq);
  g.strokeStyle = "rgba(47,213,165,.8)";
  var sq2 = Math.min(1, Math.max(0, ph * 1.6 - 0.6));
  g.strokeRect(w * 0.6, h * 0.32, w * 0.22 * sq2, h * 0.26 * sq2);
  for (var k = 0; k < 3; k++) {
    var dotPh = Math.min(1, Math.max(0, ph * 3 - k));
    if (dotPh > 0) {
      var dx = [0.26, 0.71, 0.5][k] * w, dy = [0.35, 0.45, 0.6][k] * h;
      g.fillStyle = ["rgba(255,181,71,", "rgba(47,213,165,", "rgba(63,210,240,"][k] + dotPh + ")";
      g.beginPath(); g.arc(dx, dy, 3.5 * dotPh, 0, 7); g.fill();
    }
  }
} };
})();"""

files["program.js"] = HDR.format(id="program") + """
UIP_BLOCKS.program = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var y = h * 0.55;
  g.strokeStyle = "rgba(45,59,69,1)"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(w * 0.06, y); g.lineTo(w * 0.94, y); g.stroke();
  for (var i = 0; i < 5; i++) {
    var x = w * (0.12 + i * 0.18);
    var on = (t * 0.8) % 5 >= i;
    g.strokeStyle = on ? "rgba(255,181,71,.95)" : "rgba(95,111,121,.7)";
    g.lineWidth = 2;
    g.beginPath(); g.moveTo(x, y - 10); g.lineTo(x, y + 10); g.stroke();
    if (on) { g.fillStyle = "rgba(255,181,71,.16)"; g.beginPath(); g.arc(x, y, 8, 0, 7); g.fill(); }
  }
  g.fillStyle = "rgba(255,181,71,.9)"; g.font = "9px IBM Plex Mono, monospace";
  g.fillText("INTERVENTION PROGRAM", w * 0.06, y - 18);
} };
})();"""

files["assess.js"] = HDR.format(id="assess") + """
UIP_BLOCKS.assess = { draw: function (c, w, h, t) {
  var g = c.getContext("2d");
  g.clearRect(0, 0, w, h);
  var cx = w * 0.5, cy = h * 0.55, r = Math.min(w, h) * 0.4;
  g.strokeStyle = "rgba(45,59,69,.9)";
  [0.4, 0.7, 1].forEach(function (k) { g.beginPath(); g.arc(cx, cy, r * k, 0, 7); g.stroke(); });
  var a = t * 1.8;
  g.save(); g.translate(cx, cy); g.rotate(a);
  var lg = g.createLinearGradient(0, 0, r, 0);
  lg.addColorStop(0, "rgba(47,213,165,.5)"); lg.addColorStop(1, "rgba(47,213,165,0)");
  g.fillStyle = lg;
  g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, r, -0.5, 0); g.closePath(); g.fill();
  g.strokeStyle = "rgba(47,213,165,.9)";
  g.beginPath(); g.moveTo(0, 0); g.lineTo(r, 0); g.stroke();
  g.restore();
  g.strokeStyle = "rgba(154,123,255,.5)";
  g.setLineDash([3, 4]);
  g.beginPath(); g.arc(cx, cy, r * 1.12, Math.PI * 0.6, Math.PI * 1.4); g.stroke();
  g.setLineDash([]);
} };
})();"""

for name, body in files.items():
    p = out / name
    p.write_text(body, encoding="utf-8", newline="\n")
    print(name, p.stat().st_size)
print("blocks:", len(files))
