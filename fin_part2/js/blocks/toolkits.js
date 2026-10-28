/* UIP pipeline block animation — toolkits */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

UIP_BLOCKS.toolkits = { draw: function (c, w, h, t) {
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
  if (front) {
    g.fillText("METRO POLICY", 0, -ch2 / 2 + 14);
    g.fillText("TOOLKIT", 0, -ch2 / 2 + 26);
  } else {
    g.fillText("ACTIONS", 0, -ch2 / 2 + 18);
  }
  if (!front) {
    g.fillStyle = "rgba(232,238,242,.7)";
    for (var i = 0; i < 4; i++) g.fillRect(-cw2 * 0.32, -ch2 * 0.16 + i * 16, cw2 * 0.64 * (0.6 + 0.3 * Math.sin(i * 7)), 5);
  } else {
    g.fillStyle = "rgba(232,238,242,.55)";
    g.fillRect(-cw2 * 0.3, -ch2 * 0.1, cw2 * 0.6, ch2 * 0.42);
  }
  g.restore(); g.textAlign = "left";
} };
})();