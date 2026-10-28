/* UIP pipeline block animation — program */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();