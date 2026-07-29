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

Preview locally before pushing:

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

The gradient bar under the header is a genuine cubehelix ramp, computed from
Green (2011) with the standard parameters (start 0.5, rotations -1.5, hue 1,
gamma 1), sampled at 24 points. It is not an approximation by eye. It is also
the only place green and pink still appear, because a cubehelix ramp cycles
through both by construction. A Riley-palette replacement sits commented out
directly beneath it in `style.css` if you want those gone too.

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
