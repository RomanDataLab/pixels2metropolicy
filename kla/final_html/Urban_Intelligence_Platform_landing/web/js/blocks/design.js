/* UIP pipeline block animation — design */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();