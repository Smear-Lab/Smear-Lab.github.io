#!/usr/bin/env bash
#
# Copy the site to UO Pages, so it is reachable at
#
#     https://pages.uoregon.edu/<DuckID>/
#
# This is NOT a build step. The site is plain static files and works without
# this script; it only saves you from dragging the right subset of files into
# an SFTP window by hand and, more to the point, from accidentally publishing
# the wrong ones.
#
# Usage:
#     ./deploy-to-uopages.sh              # dry run, shows what WOULD be sent
#     ./deploy-to-uopages.sh --go         # actually send it
#     DUCKID=someoneelse ./deploy-to-uopages.sh --go
#
# It refuses to do anything until you have looked at a dry run first. That is
# deliberate: --delete is on, so a wrong target directory would wipe files.

set -euo pipefail

DUCKID="${DUCKID:-smear}"          # override if your Duck ID is not this
HOST="shell.uoregon.edu"           # SSH host; SFTP-only host is sftp.uoregon.edu
REMOTE="public_html"               # UO Pages serves this folder
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Everything the published site does NOT need. Two groups: repo machinery, and
# leftovers from the React build that nothing has referenced since the rewrite.
EXCLUDES=(
  --exclude '.git'            --exclude '.gitignore'
  --exclude '.claude'         --exclude '.DS_Store'
  --exclude 'README.md'       --exclude 'site-copy.md'
  --exclude 'deploy-to-uopages.sh'
  --exclude '*.mat'                            # riley.mat, mycubehelix.mat
  --exclude 'matt_wyoming.png' --exclude 'ion_logo.png'   # full-size originals
  --exclude 'static/js'       --exclude 'static/css'      # dead React bundle
  --exclude 'asset-manifest.json'
  --exclude 'manifest.json'
  --exclude 'logo192.png'     --exclude 'logo512.png'
)

MODE="dry"
[ "${1:-}" = "--go" ] && MODE="go"

echo "source : $SRC"
echo "target : ${DUCKID}@${HOST}:~/${REMOTE}/"
echo "url    : https://pages.uoregon.edu/${DUCKID}/"
echo

if [ "$MODE" = "dry" ]; then
  echo "DRY RUN. Nothing is being copied. Re-run with --go once this list looks right."
  echo
  rsync -avn --delete "${EXCLUDES[@]}" "$SRC/" "${DUCKID}@${HOST}:${REMOTE}/"
  echo
  echo "If that list is right:  ./deploy-to-uopages.sh --go"
else
  rsync -av --delete "${EXCLUDES[@]}" "$SRC/" "${DUCKID}@${HOST}:${REMOTE}/"
  echo
  echo "Done. https://pages.uoregon.edu/${DUCKID}/"
  echo "Filenames are case sensitive on that server, so check the links."
fi
