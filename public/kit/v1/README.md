# Bad Omen kit v1

The shared look of every Bad Omen site: fonts, colors, spacing, the footer,
and the voice. bad.llc runs on it; cassie.sh and carrie.sh copy it.

Static files only. No build step, no script, no trackers, no outside requests,
so it works under a strict `default-src 'none'` CSP with `'self'` for styles
and fonts.

## Files

| File | What it is |
| --- | --- |
| `tokens.css` | `@font-face` for the four fonts and every `--bo-*` variable: color, type, spacing |
| `footer.css` | The shared footer (`.bo-foot`). Needs `tokens.css` first |
| `footer.html` | The footer markup to paste at the end of `<body>` |
| `template.html` | A starter page with both stylesheets and the footer wired in |
| `VOICE.md` | How Bad Omen copy sounds, and what it never says |
| `fonts/` | Pirata One, Geist, Geist Mono, Spectral (all OFL, licenses beside them) |

## Use it on a site

1. Copy this whole `v1` folder into the site as `kit/v1/`, so every site serves
   its own copy and needs nothing from another origin.
2. In `<head>`, before the site's own stylesheet:

       <link rel="stylesheet" href="kit/v1/tokens.css">
       <link rel="stylesheet" href="kit/v1/footer.css">

3. Paste `footer.html` at the end of `<body>`, put the site's own footer lines
   above the band, and give the site's own link `aria-current="page"`.
4. Use `var(--bo-...)` in the site's CSS rather than raw colors.

The canonical copy lives in the bad-llc repo at `public/kit/v1/` and is served
at https://bad.llc/kit/v1/.

## Versions

A folder is frozen once another site copies it. Fixes that change nothing
visible can land in place. Anything that changes the look, a token name or the
footer markup goes in a new `v2/` folder beside it, so a site moves when it
chooses to.

The one exception is the footer's link list: a new public project is added in
place, to `footer.html`, `template.html` and bad.llc together, and the other
sites recopy `footer.html`.
