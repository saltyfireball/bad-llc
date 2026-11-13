# Bad Omen kit v1

The shared look of every Bad Omen site: fonts, colors, spacing, the footer,
and the voice. bad.llc runs on it; cassie.sh and carrie.sh copy it.

Static files only. No build step, no trackers, no outside requests, so it
works under a strict `default-src 'none'` CSP with `'self'` for styles and
fonts. The optional living portrait adds `'self'` scripts and `media-src 'self'`.

## Files

| File | What it is |
| --- | --- |
| `tokens.css` | `@font-face` for the four fonts and every `--bo-*` variable: color, type, spacing |
| `footer.css` | The shared footer (`.bo-foot`). Needs `tokens.css` first |
| `footer.html` | The footer markup to paste at the end of `<body>` |
| `template.html` | A starter page with both stylesheets and the footer wired in |
| `portrait-core.js` | The living portrait's state machine (`BOPortraitCore`): blinks, eyes, clips. No DOM |
| `portrait.js` | The living portrait player for one `[data-portrait]` still. Needs `portrait-core.js` first |
| `portrait.css` | The video and canvas layers the portrait players lay over the still |
| `VOICE.md` | How Bad Omen copy sounds, and what it never says |
| `fonts/` | Pirata One, Geist, Geist Mono, Spectral (all OFL, licenses beside them) |
| `ident/` | The studio ident: a 9-second video, its poster, and the CSS and JS that play it. Optional |

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

## The studio ident

`ident/` holds the Bad Omen production logo: `ident.webm` (VP9 + Opus),
`ident.mp4` (H.264 + AAC), `ident-poster.jpg`, and `ident.css` + `ident.js`
to play it. A raven walks under a ladder. The rest follows. 9 seconds,
1920x1080. How it is made: `tools/ident/BEATS.md` in the bad-llc repo.

Load `ident/ident.css` after `tokens.css` and `ident/ident.js` with `defer`,
then put this where it goes:

    <figure class="bo-ident">
      <video muted playsinline controls preload="metadata" width="1920" height="1080"
        poster="kit/v1/ident/ident-poster.jpg"
        aria-label="Studio ident. A raven walks under a ladder. The rest follows.">
        <source src="kit/v1/ident/ident.webm" type="video/webm">
        <source src="kit/v1/ident/ident.mp4" type="video/mp4">
      </video>
      <div class="bo-ident-fallback" aria-hidden="true"><!-- optional --></div>
    </figure>

The figure takes the width of its container and reserves a 16:9 box before
anything loads, so nothing on the page moves. Give it a width in the site's
own CSS. What it does:

- First visit in a tab session: once most of it is on screen, plays once,
  muted, and stops on its last
  frame. No loop, no fade.
- Later visits (sessionStorage `bo-ident`): the poster, with a Replay button.
- `prefers-reduced-motion: reduce`: the poster, with a Play button. Nothing
  moves until someone presses it.
- "Sound: off" unmutes and plays from the start ("Sound: on" mutes again).
  While it plays, Skip jumps to the last frame. Labels are mono, uppercase.
- Without JavaScript: the poster and the browser's own controls. Nothing
  autoplays, which is why the markup has `controls` and no `autoplay`;
  the script removes `controls` and starts it itself.
- If neither file can play, `.bo-ident-fallback` shows in the same box: put
  the site's mark there, or leave it out.
- Clicks and keys elsewhere on the page leave it alone.

No captions: it has no words but the ones on screen. The site's CSP needs
`media-src 'self'` (and `img-src 'self'` for the poster), or the video is
blocked.

## Versions

A folder is frozen once another site copies it. Fixes that change nothing
visible can land in place. Anything that changes the look, a token name or the
footer markup goes in a new `v2/` folder beside it, so a site moves when it
chooses to.

The one exception is the footer's link list: a new public project is added in
place, to `footer.html`, `template.html` and bad.llc together, and the other
sites recopy `footer.html`.
