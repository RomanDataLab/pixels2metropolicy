/* UIP pipeline block animation — social */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();