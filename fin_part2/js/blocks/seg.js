/* UIP pipeline block animation — seg */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();