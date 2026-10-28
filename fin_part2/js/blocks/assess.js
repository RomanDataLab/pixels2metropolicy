/* UIP pipeline block animation — assess */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();