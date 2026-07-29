# Smear lab site

Live at <https://smear-lab.github.io/>. GitHub Pages serves the `main` branch
from the repository root, so whatever is committed to `main` is the site.

## How it works

Seven hand-written HTML files and one stylesheet. No framework, no build step,
no `npm install`. To change a word, open the file and change the word.

    index.html          home
    research.html       the four research areas
    people.html         PI, lab members, alumni
    publications.html   full list, DOI links
    outreach.html       NICE in Neuro
    join.html           openings
    contact.html        address, links
    style.css           every rule for every page

`static/media/` holds the images. The other files under `static/` are leftovers
from the previous React version of the site and nothing references them now;
they can be deleted whenever.

## Logos and image sources

Both affiliation logos sit in the footer of every page and are handled the same
way: black artwork on a transparent ground, inverted by CSS for night mode.

    static/media/uo-logo.svg    UO's own file, the one ion.uoregon.edu serves.
                                It ships white for the UO green bar, so the
                                fill was changed to near-black. That is a
                                one-colour treatment, not a redraw.
    static/media/ion-logo.png   From Matt's ion_logo.png, which is white
                                artwork on opaque black. Converted so the
                                black box becomes transparent.

To replace either, drop a new file at the same path and the CSS keeps working.
If UO Communications asks for a specific approved lockup, that is the swap.

Originals kept alongside: `riley.mat` (the palette) and `ion_logo.png` are
committed, since they record where things came from and are tiny.
`matt_wyoming.png` is gitignored at 7.5 MB; the 64 KB crop the site uses is
`static/media/matt_wyoming.jpg`.

## The one thing to watch

The masthead and the `<nav class="main">` block are **duplicated in all seven
pages**. If you add a page or rename a nav item, edit all seven. That is the
cost of having no build step, and it is cheaper than the alternative, which was
a compiled React bundle whose source no longer exists anywhere.

The current page is marked in the nav by `aria-current="page"` on its own link.
The brackets around it are drawn by CSS, so do not type them in the HTML.

## Editing

The easy way, for words rather than markup:

    python3 edit.py

That opens <http://localhost:8787>. Click into any text and type. What you are
looking at is the real page with the real stylesheet, because it is the real
page being served. Cmd+S writes it back to the HTML file. Switch pages with
the bar at the bottom.

Some deliberate limits. Only the contents of `<main>` are editable, because
the masthead, nav and footer are duplicated across all seven pages and editing
one copy here would silently desynchronise them. The editing chrome is
injected into the HTTP response and never written into the files, so nothing
about the tool can reach the live site. On save the posted markup is
sanitised: inline styles are stripped, disallowed tags are unwrapped, and the
comments in the files are preserved. A save with no edits leaves all seven
pages unchanged, which is checked rather than assumed.

**Images.** Drag a photo onto the page to add it. Drop it on a person's entry
and it replaces that person's photo, square-cropped to 500px; drop it anywhere
else and it becomes a figure with a caption, capped at 1200px on the long side.
Either way it is resized on the way in, so a 1.7 MB phone photo lands as about
76 KB rather than being published at full size. You are asked for alt text on
the way, which is not optional politeness: the accessibility standard UO
applies is WCAG 2.1 AA.

Click any image to get Replace, Alt text and Remove.

**Site-wide.** The masthead glyphs, the tagline and the affiliation line are
identical on all seven pages, so they sit outside the editable area on purpose.
The "Site-wide" button edits all seven at once, including the meta description
that repeats the tagline.

Undo is git: `git diff` shows what a save did, `git checkout -- <file>`
discards it.

**What the editor still does not reach**, by design: the nav labels, the
colour-bar caption, the footer logos, and anything in `style.css`. Those are
either structural or shared in ways that want a deliberate edit across all
seven files.

To preview without the editing chrome:

    python3 -m http.server 8123

then open <http://localhost:8123>. Opening the files directly with `file://`
mostly works too, but a real server matches what GitHub Pages does.

Publishing is just:

    git add -A && git commit -m "..." && git push

The live site updates within a minute or so.

## Design notes

Every chromatic value comes from `riley.mat`, which holds seven colours:

    #0195c3 cyan      #a983b4 muted violet   #3167d1 blue
    #c990d4 orchid    #6bb36a green          #395a7d slate    #fee098 gold

Day mode is white ground, lavender title, blue headings and links, slate for
secondary text and the current-page nav marker, gold note boxes. Night mode is
black ground, gold title and links, cyan headings, violet secondary text. The
green is deliberately unused.

The lavender is Matt's pick for the day title. It measures 3.2:1 on white,
which clears the 3:1 floor for large text but not the 4.5:1 floor for
everything else, so it belongs on the 2.1em h1 and nowhere smaller. Links
inside the gold note boxes have their own colour (`--panellink`) because the
ordinary blue only reaches 4.1:1 against that background.

Nothing outside those seven should appear. The neutral grounds and every
colour role are declared as custom properties at the top of `style.css`, so
changing the scheme means editing that one block. Contrast was measured rather
than assumed, and if you change a colour, measure it again.

The button in the header switches modes and remembers the choice in
`localStorage`; a first-time visitor gets whatever their operating system
prefers.

The gradient bar under the header is Matt's own ramp, from `mycubehelix.mat`:

    1 - CubeHelix(256, 0.5, -1, 1.5, 1.0)

The CSS stops are sampled at 25 points straight out of that file, so they are
the colormap itself rather than something that resembles it. The formula was
checked against the file first and reproduces it exactly.

Being the inverse, it runs white to black rather than black to white. That is
why the bar carries a hairline border: on the white page the left end would
otherwise disappear, and on the black page the right end would. The border
marks where the bar starts and stops without changing a colour in it.

It is also the only place green and pink appear on the site, because a
cubehelix ramp cycles through the hues by construction. That is the scheme,
and it is a deliberate choice, not an oversight.

Everything is Arial, by house rule. There is exactly one `font-family`
declaration in the whole stylesheet, on `body`, and nothing else should add
one. Because the serif and monospace contrast is gone, small labels (nav, the
role line under a name, publication years, tags) carry their distinction with
letter-spacing, weight, and small caps instead.

House style for anything written here: no em-dashes, sentence case, "by mice"
rather than "in mice". Published paper titles on `publications.html` are quoted
exactly as printed and are deliberately exempt.

## Still to fill in

Search the HTML for `TODO` and for `class="todo"`. The `todo` spans are styled
so unfinished text is visible on the page rather than hidden in a comment.
Current gaps: alumni years and destinations, Lila Kaye's project line, the
Huestis Hall painting credit, postdoc openings, journal club details, and news
items.
