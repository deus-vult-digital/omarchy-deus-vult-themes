#!/usr/bin/env bash
# Push built themes (tools/build.py) to their own repos, one commit each.
#
#   tools/publish.sh -m "Amber: warmer muted" [-p] [phosphor…]   # default: all built
#
# Each build/deus-vult-<phosphor>/ goes to omarchy-deus-vult-<phosphor>-theme,
# a repo next to this one: same remote host and owner as this repo's origin.
# A repo that doesn't exist yet is created by the first push (push-to-create).
# A working clone is kept in build/repos/; its files are
# replaced by the build's (so a file the build no longer makes is removed),
# committed with this repo's git identity in UTC, and pushed to main. A theme
# whose files didn't change gets no commit.
#
# -p also pushes main to the theme's public mirror,
# https://github.com/deus-vult-digital/<repo> (which must exist). Only with the
# owner's go-ahead: the mirror is what `omarchy theme install` users get.
set -euo pipefail

repo=$(git -C "$(dirname -- "$(realpath -- "$0")")" rev-parse --show-toplevel)
message= public=
mirror=https://github.com/deus-vult-digital
while getopts m:p opt; do
  case $opt in
    m) message=$OPTARG ;;
    p) public=1 ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))
[[ -n $message ]] || { echo "publish: give a commit message with -m" >&2; exit 2; }

origin=$(git -C "$repo" remote get-url origin)
base=${origin%/*}
name=$(git -C "$repo" config user.name)
email=$(git -C "$repo" config user.email)

if (($#)); then
  keys=("$@")
else
  keys=()
  for dir in "$repo"/build/deus-vult-*/; do
    [[ -d $dir ]] && keys+=("$(basename "$dir" | sed 's/^deus-vult-//')")
  done
fi
((${#keys[@]})) || { echo "publish: nothing built; run tools/build.py" >&2; exit 1; }

for key in "${keys[@]}"; do
  src="$repo/build/deus-vult-$key"
  target="omarchy-deus-vult-$key-theme"
  work="$repo/build/repos/$target"
  [[ -f $src/colors.toml && -f $src/preview.png ]] ||
    { echo "publish: $src is not a full build (tools/build.py $key, without --quick)" >&2; exit 1; }
  if [[ ! -d $work/.git ]]; then
    if git ls-remote -q "$base/$target.git" >/dev/null 2>&1; then
      git clone -q "$base/$target.git" "$work"
    else # not there yet: the first push creates it (Forgejo push-to-create, private)
      git init -q -b main "$work"
      git -C "$work" remote add origin "$base/$target.git"
    fi
  fi
  if git -C "$work" ls-remote -q origin >/dev/null 2>&1; then
    git -C "$work" fetch -q origin
    if git -C "$work" rev-parse -q --verify origin/main >/dev/null; then
      git -C "$work" checkout -q -B main origin/main
    fi
  fi
  find "$work" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -a "$src/." "$work/"
  git -C "$work" add -A
  if git -C "$work" diff --cached --quiet; then
    echo "publish: $target unchanged"
  else
    TZ=UTC git -C "$work" -c user.name="$name" -c user.email="$email" commit -q -m "$message"
    git -C "$work" push -q origin main
    echo "publish: $target $(git -C "$work" rev-parse --short HEAD)"
  fi
  if [[ -n $public ]]; then
    git -C "$work" push -q "$mirror/$target.git" main
    echo "publish: $mirror/$target $(git -C "$work" rev-parse --short HEAD)"
  fi
done
