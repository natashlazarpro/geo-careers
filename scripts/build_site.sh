#!/bin/sh
# Builds the website into public/ and inserts the Mapbox token from the
# Cloudflare build secret MAPBOX_TOKEN (the token is not stored in the repo).
set -e
if [ -z "$MAPBOX_TOKEN" ]; then
  echo "ERROR: MAPBOX_TOKEN is not set. Add it in Cloudflare: geo-careers → Settings → Build → Variables and secrets." >&2
  exit 1
fi
mkdir -p public
sed "s|__MAPBOX_TOKEN__|$MAPBOX_TOKEN|" index.html > public/index.html
# Favicons (browser tab icon, iPhone home-screen icon)
cp icons/* public/
