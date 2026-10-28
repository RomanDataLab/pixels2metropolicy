/* UIP pipeline block animation — match */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();