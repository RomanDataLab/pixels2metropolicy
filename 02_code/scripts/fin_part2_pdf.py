"""Export fin_part2 (JS-built HTML page) to a paginated PDF.

Pipeline:
  1. serve repo root over localhost HTTP (page fetch()es data/*.json and
     embeds repo-root iframes like /slum.html — file:// would break both)
  2. headless Chrome (system install, via Playwright channel="chrome")
  3. scroll through the page so IntersectionObserver reveals fire,
     then force-reveal everything as a safety net
  4. freeze hover/fixed chrome (pipenav, floatpanel, tooltip), pause videos
     on their poster frame, wait for embedded iframes to settle
  5. page.pdf() with screen media emulated so the dark theme prints

Usage:
  py -3.13 02_code/scripts/fin_part2_pdf.py [out.pdf]

Requires: py -3.13 -m pip install playwright pypdfium2
(Playwright pip package only — no browser download, uses installed Chrome.)
"""

import http.server
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
PAGE_PATH = "/fin_part2/"
DEFAULT_OUT = REPO / "04_output" / "fin_part2" / "fin_part2.pdf"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_error(self, request, client_address):
        # Chrome aborts media/range requests mid-stream; not an error for us
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO), **kwargs)


def serve():
    socketserver.TCPServer.allow_reuse_address = True
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), QuietHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def export(out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    httpd, port = serve()
    url = f"http://127.0.0.1:{port}{PAGE_PATH}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(url, wait_until="networkidle", timeout=60000)

            # sections are built from fetched JSON after load
            page.wait_for_selector("#sections section", timeout=30000)
            page.wait_for_timeout(1500)

            # scroll through: triggers IntersectionObserver .reveal and
            # lazy iframe loads
            height = page.evaluate("document.body.scrollHeight")
            step = 900
            for y in range(0, height + step, step):
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(220)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(400)

            # safety net: reveal anything the observer missed, drop the
            # transition so nothing is caught mid-fade
            page.add_style_tag(content="""
                .reveal{opacity:1 !important;transform:none !important;transition:none !important}
                #pipenav,#floatpanel,#tooltip{display:none !important}
                /* never slice a map / video / card block across pages:
                   every atomic block moves whole to the next page instead */
                .pipewrap,.pnode,
                .s-head,.proc,.step,
                .embedbox,.vidbox,.mapbox,
                .tblwrap,.pgroup,.ghead,.caro-wrap,.pcard,
                #toolkitsnap,#toolkitsnap .kpick,#toolkitdetail,
                .toolkitrows .kflip,#bezier,
                .mapctl,.pdfkeep,.intv-card,
                details.rollup summary
                {break-inside:avoid}
                /* Chrome print rasterizes preserve-3d flip cards rotated 180deg:
                   stack both toolkit faces statically (readable), keep map
                   overlay cards on their front face only */
                .kflip{height:auto !important;perspective:none !important}
                .kflip .inner{transform:none !important;transform-style:flat !important;height:auto !important}
                .kflip .kface{position:static !important;transform:none !important;
                              backface-visibility:visible !important;height:auto !important}
                .kflip .kface.back{transform:none !important}
                .intv-card{perspective:none !important}
                .intv-card .inner{transform:none !important;transform-style:flat !important}
                .intv-card .face.back{display:none !important}
            """)

            # keep the design map and its layer chips on the same page
            page.evaluate("""
                const dn = document.getElementById('dnmap');
                if (dn) {
                    const w = dn.closest('div.reveal');
                    if (w) { w.classList.add('pdfkeep');
                             w.style.breakInside = 'avoid'; }
                }
            """)

            # pause videos on their poster/first frame so they print as
            # stills instead of black boxes
            page.evaluate("""
                document.querySelectorAll('video').forEach(v => {
                    v.pause();
                    if (!v.poster && v.readyState === 0) v.load();
                });
            """)
            page.wait_for_timeout(1200)

            # embedded maps are separate pages inside iframes — give them
            # time to fetch their own tiles/data
            deadline = time.time() + 45
            while time.time() < deadline:
                settled = page.evaluate("""
                    (() => {
                      const fr = document.querySelectorAll('.embedbox iframe');
                      let busy = 0;
                      fr.forEach(f => {
                        try {
                          if (f.contentDocument.readyState !== 'complete') busy++;
                        } catch (e) { /* cross-origin: assume loaded */ }
                      });
                      return fr.length && !busy;
                    })()
                """)
                if settled:
                    break
                page.wait_for_timeout(1000)
            page.wait_for_timeout(2500)

            # screen media: keep the dark theme layout instead of print CSS
            page.emulate_media(media="screen")
            page.pdf(
                path=str(out_path),
                width="1440px",
                height="1018px",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            browser.close()
    finally:
        httpd.shutdown()

    print(f"PDF written: {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    export(out)
