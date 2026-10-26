/* UIP pipeline block animation — rank */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();