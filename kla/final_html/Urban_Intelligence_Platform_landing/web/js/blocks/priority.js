/* UIP pipeline block animation — priority */
(function(){
window.UIP_BLOCKS = window.UIP_BLOCKS || {};

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
})();