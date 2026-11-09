# bad-llc

The landing page for https://bad.llc, home of Bad Omen: one static page, hosted on Cloudflare Pages.

Everything in this repo ends up public. Keep hostnames, IPs, internal URLs, secrets, private details and licensed assets out of it. Art is hand-made SVG; fonts are OFL and self-hosted, with their licenses in `public/kit/v1/fonts/`.

Epic: SLRM-1779

## The Bad Omen kit

`public/kit/v1/` is the shared kit every Bad Omen site uses: fonts, the `--bo-*`
color, type and spacing tokens, the shared footer, a starter page and the voice
guide (`VOICE.md`). bad.llc loads it like any other site would; cassie.sh and
carrie.sh copy the folder. Its own README covers using it and when a change
needs a `v2/`. Epic: SLRM-1881.

## Updating the page

1. Edit the files in `public/` directly. There is no build step. JavaScript is tiny, deferred and only for easter eggs; the page works without it.
2. To check it locally, serve `public/` with any static server.
3. Run `./deploy.sh` to publish `public/` to the preview, https://preview.bad-llc-ncd.pages.dev. `./deploy.sh main` publishes production, and only after John signs off.

`deploy.sh` never attaches domains or touches DNS. bad.llc carries live Proton Mail records (MX, SPF, DKIM, DMARC): leave them alone.

Text is readable on first paint. The studio ident never blocks it, runs once, skips on a click or key, and is off under `prefers-reduced-motion`.

`no-transform` in `public/_headers` is there on purpose: it stops Cloudflare adding its analytics script to the page.
