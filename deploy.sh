#!/usr/bin/env bash
# Publish public/ to the Cloudflare Pages project bad-llc. There is no build step.
# The token comes from Infisical and is never printed.
#
# usage: ./deploy.sh            deploys the preview branch: https://preview.bad-llc.pages.dev
#        ./deploy.sh main       deploys production (only after John signs off, SLRM-1786)
#
# This script only uploads files. It never attaches domains or touches DNS: bad.llc carries
# live Proton Mail records (MX, SPF, DKIM, DMARC).
set -euo pipefail

cd "$(dirname "$0")"
branch="${1:-preview}"

CLOUDFLARE_API_TOKEN="$(secret get CF_PAGES_TOKEN)"
export CLOUDFLARE_API_TOKEN

CLOUDFLARE_ACCOUNT_ID="$(curl -fsS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=bad.llc" | jq -er '.result[0].account.id')"
export CLOUDFLARE_ACCOUNT_ID

# Cloudflare gives CSS and JS a 4 hour browser cache whatever _headers says, while the page
# itself is never cached. So a deploy publishes a copy whose pages point at each file by the
# hash of its content: changed content is a new URL.
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp -R public/. "$stage/"
for asset in style.css omen.js; do
  [ -f "public/$asset" ] || continue
  hash="$(shasum -a 256 "public/$asset" | cut -c1-12)"
  for page in "$stage"/*.html; do
    sed -i '' "s|\"$asset\"|\"$asset?v=$hash\"|" "$page"
  done
done

npx --yes wrangler@4 pages deploy "$stage" --project-name bad-llc --branch "$branch"
