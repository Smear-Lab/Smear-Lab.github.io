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

import base64
import http.server
import io
import json
import re
import socketserver
import unicodedata
import webbrowser
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT / "static" / "media"
PORT = 8787

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

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
        kept = []
        for k, v in attrs:
            if k not in OK_ATTRS or v is None:
                continue
            if k == "class":
                # the editor marks the selected image with __sel; anything
                # it adds is prefixed __ and must never reach the file
                v = " ".join(c for c in v.split() if not c.startswith("__"))
                if not v:
                    continue
            kept.append((k, v))
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

# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------

def slug(name):
    stem = Path(name).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return stem or "image"


def save_image(filename, raw, mode):
    """Write an uploaded image into static/media/, sized for how it is used.

    mode 'portrait' is a person photo: square crop, 500px, matching the
    110px thumbnail the stylesheet renders it at on retina screens.
    mode 'figure' is anything else: longest side capped at 1200px.

    Photos off a phone are routinely 5-10 MB, which is absurd to publish for
    something displayed 110px wide, so this is not optional politeness.
    """
    MEDIA.mkdir(parents=True, exist_ok=True)
    base = slug(filename)

    if not HAVE_PIL:
        # Better to store the original than to refuse the upload; say so.
        ext = Path(filename).suffix.lower() or ".jpg"
        path = unique(base, ext)
        path.write_bytes(raw)
        return rel(path), "saved at full size (Pillow not installed)"

    im = Image.open(io.BytesIO(raw))
    has_alpha = im.mode in ("RGBA", "LA", "P") and "transparency" in im.info \
        or im.mode in ("RGBA", "LA")
    before = len(raw)

    if mode == "portrait":
        im = im.convert("RGBA" if has_alpha else "RGB")
        w, h = im.size
        side = min(w, h)
        im = im.crop(((w - side) // 2, (h - side) // 2,
                      (w - side) // 2 + side, (h - side) // 2 + side))
        im = im.resize((500, 500), Image.LANCZOS)
    else:
        im = im.convert("RGBA" if has_alpha else "RGB")
        im.thumbnail((1200, 1200), Image.LANCZOS)

    buf = io.BytesIO()
    if has_alpha:
        im.save(buf, "PNG", optimize=True)
        path = unique(base, ".png")
    else:
        im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
        path = unique(base, ".jpg")
    path.write_bytes(buf.getvalue())
    note = f"{before // 1024} KB to {len(buf.getvalue()) // 1024} KB"
    return rel(path), note


def unique(base, ext):
    p = MEDIA / f"{base}{ext}"
    n = 2
    while p.exists():
        p = MEDIA / f"{base}-{n}{ext}"
        n += 1
    return p


def rel(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


# ---------------------------------------------------------------------------
# the bits that are identical on every page
# ---------------------------------------------------------------------------

SHARED = {
    "glyphs": (re.compile(r'(<p class="glyphs" aria-hidden="true">)(.*?)(</p>)'), None),
    "tagline": (re.compile(r'(<p class="tagline">)(.*?)(</p>)'), None),
    "affil": (re.compile(r'(<p class="affil">)(.*?)(</p>)'), None),
}


def read_shared():
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    return {k: rx.search(src).group(2) for k, (rx, _) in SHARED.items()}


def write_shared(values):
    """Apply to all seven pages at once. These live outside <main> precisely
    because they are duplicated, so editing one copy in the page editor would
    desynchronise the rest. This is the safe way to change them."""
    changed = []
    old_tagline = read_shared()["tagline"]
    for page in PAGES:
        f = ROOT / page
        src = f.read_text(encoding="utf-8")
        new = src
        for key, (rx, _) in SHARED.items():
            if key in values:
                new = rx.sub(
                    lambda m, v=values[key]: m.group(1) + v + m.group(3),
                    new, count=1)
        # the tagline is also the tail of every page's meta description
        if "tagline" in values and old_tagline:
            new = new.replace(f"University of Oregon. {old_tagline}.",
                              f"University of Oregon. {values['tagline']}.")
        if new != src:
            f.write_text(new, encoding="utf-8")
            changed.append(page)
    return changed

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
  main img { cursor: pointer; }
  main img.__sel { outline: 3px solid #ffd479; outline-offset: 2px; }
  #__drop { position: fixed; inset: 0; z-index: 99998; display: none;
    background: rgba(20,60,40,.55); border: 4px dashed #7de0a5;
    color: #fff; font: bold 22px Arial, sans-serif;
    align-items: center; justify-content: center; }
  #__drop.on { display: flex; }
  #__tools, #__panel { position: fixed; z-index: 100000; background: #111;
    border: 1px solid #555; border-radius: 4px; padding: 6px;
    font: 13px Arial, sans-serif; color: #eee; display: none; gap: 6px; }
  #__tools.on { display: flex; }
  #__panel { right: 12px; bottom: 52px; flex-direction: column; width: 340px;
    padding: 12px; }
  #__panel.on { display: flex; }
  #__panel label { font-size: 12px; opacity: .8; margin-top: 6px; }
  #__panel input { font: 14px Arial, sans-serif; padding: 5px;
    background: #1e1e1e; color: #eee; border: 1px solid #555; border-radius: 3px; }
  #__tools button, #__panel button { font: 12px Arial, sans-serif;
    padding: 4px 9px; cursor: pointer; border-radius: 3px;
    border: 1px solid #555; background: #2a2a2a; color: #eee; }
  #__panel .hint { font-size: 11px; opacity: .6; margin-top: 8px; line-height: 1.4 }
</style>
<div id="__drop">drop to add the image here</div>
<div id="__tools">
  <button id="__t-replace">Replace</button>
  <button id="__t-alt">Alt text</button>
  <button id="__t-del">Remove</button>
</div>
<div id="__panel">
  <b>Site-wide</b>
  <label>masthead glyphs</label><input id="__p-glyphs">
  <label>tagline</label><input id="__p-tagline">
  <label>affiliation line</label><input id="__p-affil">
  <button id="__p-apply" style="margin-top:10px">Apply to all 7 pages</button>
  <div class="hint">These three sit outside the editable area because they are
    duplicated on every page. Changing them here rewrites all seven at once,
    plus the meta description. Save any page edits first.</div>
</div>
<div id="__bar">
  <span>edit:</span>
  __LINKS__
  <span class="sp"></span>
  <span id="__warn"></span>
  <span id="__st">saved</span>
  <button id="__sitewide">Site-wide...</button>
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
    if (sel) { sel.classList.remove('__sel'); }   /* never persist the marker */
    tools.classList.remove('on');
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

  /* ---- images ---------------------------------------------------------- */

  var sel = null;                       /* currently clicked <img> */
  var tools = document.getElementById('__tools');
  var drop = document.getElementById('__drop');

  function pickImage(cb) {
    var inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = function () { if (inp.files[0]) cb(inp.files[0]); };
    inp.click();
  }

  /* A photo inside a .person is a 110px square thumbnail; anything else is a
     figure. Telling the server which lets it crop and size appropriately. */
  function modeFor(node) {
    return node && node.closest && node.closest('.person') ? 'portrait' : 'figure';
  }

  function upload(file, mode, cb) {
    st.textContent = 'uploading ' + file.name + '...';
    var fr = new FileReader();
    fr.onload = function () {
      fetch('/__upload', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: file.name, data: fr.result, mode: mode})
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j.ok) { st.textContent = 'ERROR: ' + j.error; return; }
        st.textContent = 'added ' + j.path + '  (' + j.note + ')';
        cb(j.path);
        mark();
      });
    };
    fr.readAsDataURL(file);
  }

  function askAlt(current) {
    var a = window.prompt(
      'Alt text. Describe the image for someone who cannot see it. ' +
      'Leave empty only if it is purely decorative.', current || '');
    return a === null ? current || '' : a;
  }

  main.addEventListener('click', function (e) {
    if (e.target.tagName === 'IMG') {
      if (sel) sel.classList.remove('__sel');
      sel = e.target;
      sel.classList.add('__sel');
      var r = sel.getBoundingClientRect();
      tools.style.left = Math.round(r.left) + 'px';
      tools.style.top = Math.round(r.bottom + 6) + 'px';
      tools.classList.add('on');
    } else if (sel) {
      sel.classList.remove('__sel'); sel = null; tools.classList.remove('on');
    }
  });

  document.getElementById('__t-replace').addEventListener('click', function () {
    if (!sel) return;
    pickImage(function (f) {
      upload(f, modeFor(sel), function (path) { sel.setAttribute('src', path); });
    });
  });
  document.getElementById('__t-alt').addEventListener('click', function () {
    if (!sel) return;
    sel.setAttribute('alt', askAlt(sel.getAttribute('alt'))); mark();
  });
  document.getElementById('__t-del').addEventListener('click', function () {
    if (!sel) return;
    var fig = sel.closest('figure');
    (fig || sel).remove();
    sel = null; tools.classList.remove('on'); mark();
  });

  /* drag a file anywhere onto the page to add it */
  var depth = 0;
  document.addEventListener('dragenter', function (e) {
    if (e.dataTransfer && e.dataTransfer.types.indexOf('Files') > -1) {
      depth++; drop.classList.add('on');
    }
  });
  document.addEventListener('dragleave', function () {
    if (--depth <= 0) { depth = 0; drop.classList.remove('on'); }
  });
  document.addEventListener('dragover', function (e) { e.preventDefault(); });
  document.addEventListener('drop', function (e) {
    e.preventDefault(); depth = 0; drop.classList.remove('on');
    var f = e.dataTransfer.files[0];
    if (!f || f.type.indexOf('image/') !== 0) return;
    var over = document.elementFromPoint(e.clientX, e.clientY);
    var person = over && over.closest ? over.closest('.person') : null;
    upload(f, person ? 'portrait' : 'figure', function (path) {
      var alt = askAlt('');
      if (person) {
        var existing = person.querySelector('img');
        if (existing) { existing.setAttribute('src', path); existing.setAttribute('alt', alt); }
        else {
          var img = document.createElement('img');
          img.src = path; img.alt = alt;
          person.insertBefore(img, person.firstChild);
        }
      } else {
        var fig = document.createElement('figure');
        fig.innerHTML = '<img src="' + path + '" alt="' + alt.replace(/"/g, '&quot;') +
                        '"><figcaption>caption</figcaption>';
        main.appendChild(fig);
        fig.scrollIntoView({block: 'center'});
      }
    });
  });

  /* ---- the bits shared by all seven pages ------------------------------ */

  var panel = document.getElementById('__panel');
  document.getElementById('__sitewide').addEventListener('click', function () {
    if (panel.classList.contains('on')) { panel.classList.remove('on'); return; }
    fetch('/__shared').then(function (r) { return r.json(); }).then(function (j) {
      document.getElementById('__p-glyphs').value = j.glyphs;
      document.getElementById('__p-tagline').value = j.tagline;
      document.getElementById('__p-affil').value = j.affil;
      panel.classList.add('on');
    });
  });
  document.getElementById('__p-apply').addEventListener('click', function () {
    fetch('/__shared', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        glyphs: document.getElementById('__p-glyphs').value,
        tagline: document.getElementById('__p-tagline').value,
        affil: document.getElementById('__p-affil').value
      })
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (!j.ok) { st.textContent = 'ERROR: ' + j.error; return; }
      st.textContent = 'updated ' + j.changed.length + ' pages, reloading';
      panel.classList.remove('on');
      setTimeout(function () { location.reload(); }, 600);
    });
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
        if path == "/__shared":
            self._json(read_shared())
            return
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
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)

        if self.path == "/__upload":
            try:
                req = json.loads(raw)
                data = base64.b64decode(req["data"].split(",", 1)[-1])
                path, note = save_image(req["name"], data,
                                        req.get("mode", "figure"))
                print(f"  image {path}  ({note})")
                self._json({"ok": True, "path": path, "note": note})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
            return

        if self.path == "/__shared":
            try:
                req = json.loads(raw)
                changed = write_shared(req)
                print(f"  site-wide edit applied to {len(changed)} pages")
                self._json({"ok": True, "changed": changed})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
            return

        if self.path != "/__save":
            self.send_error(404)
            return
        try:
            req = json.loads(raw)
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
