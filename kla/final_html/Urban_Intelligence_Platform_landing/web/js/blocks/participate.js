/* UIP pipeline block animation — participate */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();