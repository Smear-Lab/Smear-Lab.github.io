#!/usr/bin/env python3
"""
Edit the site's words in the browser, in the finished page, and save to disk.

    python3 edit.py

Then open http://localhost:8787 and click into any text. What you see is the
real page with the real stylesheet, because it IS the real page: this serves
the actual files. Cmd+S saves back to the HTML.

The editing chrome is injected into the HTTP RESPONSE, never written into the
files. Nothing about this tool can end up on the live site, and the .html on
disk stays exactly as hand-written apart from the words you change.

Only the contents of <main> are editable. The masthead, nav and footer are
identical across all seven pages, so editing them here would silently
desynchronise them; change those by hand in all seven files.

Undo is git. Save something you regret and `git diff` shows it,
`git checkout -- <file>` throws it away.

One harmless quirk: the first save on a page turns decorative HTML entities
into the characters themselves, so `&middot;` becomes a literal `·`. The page
is UTF-8 and renders identically either way. `&amp;`, `&lt;` and `&gt;` are
NOT affected; the browser keeps those escaped, as it must.
"""

import http.server
import json
import re
import socketserver
import webbrowser
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8787

PAGES = ["index.html", "research.html", "people.html", "publications.html",
         "outreach.html", "join.html", "contact.html"]

# What may survive a save. Anything else is unwrapped, keeping its text.
OK_TAGS = {"p", "h2", "h3", "h4", "ul", "ol", "li", "a", "b", "strong", "i",
           "em", "br", "hr", "div", "span", "figure", "figcaption", "img",
           "blockquote"}
# Attributes worth keeping. `style` is deliberately absent: contenteditable
# loves to sprinkle inline styles, and every colour on this site comes from
# style.css by design.
OK_ATTRS = {"class", "href", "src", "alt", "title"}
VOID = {"br", "hr", "img"}


class Clean(HTMLParser):
    """Rebuild the posted fragment with only the allowed tags and attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.dropped = []
        self.open = []      # what we actually emitted, so ends match starts
        self.mute = 0       # inside <script>/<style>: swallow the text too

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.dropped.append(tag)
            self.mute += 1
            return
        if tag not in OK_TAGS:
            self.dropped.append(tag)
            return
        # Divs are left alone. It is tempting to rewrite a bare <div> into a
        # <p>, since that is what a browser emits for a new block, but the
        # site uses unclassed divs structurally (the right-hand column of a
        # .person entry) and rewriting those breaks the layout. The editor
        # sets defaultParagraphSeparator to 'p' instead, which fixes the
        # cause rather than patching the symptom here.
        kept = [(k, v) for k, v in attrs if k in OK_ATTRS and v is not None]
        s = "".join(f' {k}="{v}"' for k, v in kept)
        self.out.append(f"<{tag}{s}>")
        if tag not in VOID:
            self.open.append((tag, tag))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.mute = max(0, self.mute - 1)
            return
        if tag not in OK_TAGS or tag in VOID:
            return
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i][0] == tag:
                self.out.append(f"</{self.open[i][1]}>")
                del self.open[i]
                return

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, d):
        if not self.mute:
            self.out.append(d)

    def handle_entityref(self, n):
        if not self.mute:
            self.out.append(f"&{n};")

    def handle_charref(self, n):
        if not self.mute:
            self.out.append(f"&#{n};")

    def handle_comment(self, c):
        # Comments carry the notes about what must not be changed, notably
        # "Leah Blankenship and Lila Kaye are NOT lab members" on people.html.
        # Dropping them on the first save would quietly delete the guardrails.
        if not self.mute:
            self.out.append(f"<!--{c}-->")

    def close(self):
        super().close()
        while self.open:                      # anything left unclosed
            self.out.append(f"</{self.open.pop()[1]}>")


def sanitize(fragment):
    p = Clean()
    p.feed(fragment)
    p.close()
    html = "".join(p.out)
    html = re.sub(r"<p>\s*</p>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip(), sorted(set(p.dropped))


MAIN_RE = re.compile(r'(<main id="main">)(.*?)(</main>)', re.S)

EDITOR = """
<style id="__ed">
  #__bar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 99999;
    background: #111; color: #eee; font: 13px Arial, sans-serif;
    padding: 8px 12px; display: flex; gap: 10px; align-items: center;
    box-shadow: 0 -2px 12px rgba(0,0,0,.4); }
  #__bar a { color: #8ecdf5; text-decoration: none; padding: 2px 5px; }
  #__bar a.cur { color: #ffd479; font-weight: bold; }
  #__bar .sp { flex: 1 }
  #__bar button { font: 13px Arial, sans-serif; padding: 4px 12px;
    cursor: pointer; border-radius: 3px; border: 1px solid #555;
    background: #2a2a2a; color: #eee; }
  #__bar button.on { background: #1e6f3e; border-color: #2e9d59; color: #fff; }
  #__st { opacity: .75 }
  #__warn { color: #ffb3b3 }
  body { padding-bottom: 60px !important; }
  main[contenteditable="true"] { outline: 2px dashed rgba(140,140,140,.45);
    outline-offset: 10px; }
</style>
<div id="__bar">
  <span>edit:</span>
  __LINKS__
  <span class="sp"></span>
  <span id="__warn"></span>
  <span id="__st">saved</span>
  <button id="__save">Save  (Cmd+S)</button>
</div>
<script>
(function () {
  var main = document.getElementById('main');
  var st = document.getElementById('__st');
  var warn = document.getElementById('__warn');
  var btn = document.getElementById('__save');
  var dirty = false;

  main.setAttribute('contenteditable', 'true');
  main.setAttribute('spellcheck', 'true');
  try { document.execCommand('defaultParagraphSeparator', false, 'p'); } catch (e) {}

  function mark() {
    if (!dirty) { dirty = true; st.textContent = 'unsaved'; btn.classList.add('on'); }
    checkDashes();
  }
  function checkDashes() {
    warn.textContent = main.innerText.indexOf('\\u2014') > -1
      ? 'contains an em-dash' : '';
  }
  main.addEventListener('input', mark);

  function save() {
    st.textContent = 'saving...';
    fetch('/__save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({page: '__PAGE__', html: main.innerHTML})
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (j.ok) {
        dirty = false;
        btn.classList.remove('on');
        st.textContent = 'saved' + (j.dropped.length
          ? ' (removed stray ' + j.dropped.join(', ') + ')' : '');
      } else {
        st.textContent = 'ERROR: ' + j.error;
      }
    }).catch(function (e) { st.textContent = 'ERROR: ' + e; });
  }
  btn.addEventListener('click', save);
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); save(); }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });
  checkDashes();
})();
</script>
"""


def links(current):
    out = []
    for p in PAGES:
        cls = ' class="cur"' if p == current else ""
        out.append(f'<a href="/{p}"{cls}>{p[:-5]}</a>')
    return "\n  ".join(out)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        name = path.lstrip("/") or "index.html"
        if name in PAGES:
            src = (ROOT / name).read_text(encoding="utf-8")
            chrome = EDITOR.replace("__PAGE__", name).replace("__LINKS__", links(name))
            body = src.replace("</body>", chrome + "\n</body>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/__save":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n))
            page = req["page"]
            if page not in PAGES:
                raise ValueError(f"unknown page {page!r}")
            clean, dropped = sanitize(req["html"])
            f = ROOT / page
            src = f.read_text(encoding="utf-8")
            if not MAIN_RE.search(src):
                raise ValueError("no <main id=\"main\"> block found")
            new = MAIN_RE.sub(
                lambda m: m.group(1) + "\n" + clean + "\n" + m.group(3),
                src, count=1)
            f.write_text(new, encoding="utf-8")
            print(f"  saved {page}" + (f"  (dropped {dropped})" if dropped else ""))
            self._json({"ok": True, "dropped": dropped})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as srv:
        url = f"http://localhost:{PORT}/"
        print(f"\n  Editing {ROOT.name}")
        print(f"  {url}")
        print("\n  Click into the text. Cmd+S saves. Ctrl+C here stops.")
        print("  Only <main> is editable. Undo is git.\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped\n")
