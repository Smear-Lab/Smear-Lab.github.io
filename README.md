# Smear Lab site

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

## The one thing to watch

The masthead and the `<nav class="main">` block are **duplicated in all seven
pages**. If you add a page or rename a nav item, edit all seven. That is the
cost of having no build step, and it is cheaper than the alternative, which was
a compiled React bundle whose source no longer exists anywhere.

The current page is marked in the nav by `aria-current="page"` on its own link.
The brackets around it are drawn by CSS, so do not type them in the HTML.

## Editing

Preview locally before pushing:

    python3 -m http.server 8123

then open <http://localhost:8123>. Opening the files directly with `file://`
mostly works too, but a real server matches what GitHub Pages does.

Publishing is just:

    git add -A && git commit -m "..." && git push

The live site updates within a minute or so.

## Design notes

Day mode is a homage to Dave Green's cubehelix page: pale background, dark red
title, ordinary blue links. Night mode is the other reference point: black
page, neon ink, glowing links. The button in the header switches
between them and remembers the choice in `localStorage`; a first-time visitor
gets whatever their operating system prefers.

The gradient bar under the header is a genuine cubehelix ramp, computed from
Green (2011) with the standard parameters (start 0.5, rotations -1.5, hue 1,
gamma 1), sampled at 24 points. It is not an approximation by eye.

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
