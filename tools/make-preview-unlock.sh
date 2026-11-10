#!/usr/bin/env bash
# preview-unlock.png: the disk-unlock (Plymouth) screen a built theme gives,
# at 1920x1080, composed the way Omarchy's omarchy.script lays it out:
# unlock.png centred, the password entry 40 px under it, the lock to its left,
# four bullets typed. Colours as omarchy-plymouth-set-by-theme takes them:
# background and foreground from colors.toml; the entry, lock and bullet
# images are Omarchy's own, tinted to the foreground.
#
#   tools/make-preview-unlock.sh build/deus-vult-green-screen
set -euo pipefail

theme=${1:?usage: make-preview-unlock.sh <theme folder>}
OMARCHY_PATH=${OMARCHY_PATH:-/usr/share/omarchy}
assets=$OMARCHY_PATH/default/plymouth
bg=$(omarchy-theme-color --file "$theme/colors.toml" background)
fg=$(omarchy-theme-color --file "$theme/colors.toml" foreground)

W=1920 H=1080
read -r lw lh < <(magick identify -format '%w %h\n' "$theme/unlock.png")
read -r ew eh < <(magick identify -format '%w %h\n' "$assets/entry.png")
lx=$(((W - lw) / 2)) ly=$(((H - lh) / 2))
ex=$(((W - ew) / 2)) ey=$((ly + lh + 40))
# The lock is scaled to 0.8 of the entry's height, keeping its 84x96 shape.
kh=$((eh * 8 / 10)) kw=$((84 * eh * 8 / 10 / 96))
kx=$((ex - kw - 15)) ky=$((ey + (eh - kh) / 2))
by=$((ey + eh / 2 - 3))

tint() { magick "$1" -channel RGB +level-colors "$fg,$fg" +channel "${@:2}"; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tint "$assets/entry.png" "$tmp/entry.png"
tint "$assets/lock.png" -resize "${kw}x${kh}!" "$tmp/lock.png"
tint "$assets/bullet.png" -resize 7x7 "$tmp/bullet.png"

args=(-size "${W}x${H}" "xc:$bg"
  "$theme/unlock.png" -geometry "+$lx+$ly" -composite
  "$tmp/entry.png" -geometry "+$ex+$ey" -composite
  "$tmp/lock.png" -geometry "+$kx+$ky" -composite)
for i in 0 1 2 3; do
  args+=("$tmp/bullet.png" -geometry "+$((ex + 20 + i * 12))+$by" -composite)
done
magick "${args[@]}" -depth 8 -strip "$theme/preview-unlock.png"
echo "make-preview-unlock: $theme/preview-unlock.png"
