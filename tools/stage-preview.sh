#!/usr/bin/env bash
# Stage an isolated Omarchy desktop on this theme and capture preview.png, the
# way the stock themes' previews look: the bar, three tiled terminals
# (fastfetch and a git diff, btop, a source file) on one of the backgrounds.
#
# Adapted from Omavisor's docs/preview/stage.sh. Nothing of the real session
# is read or changed:
#   - own HOME, XDG_{CONFIG,STATE,CACHE,DATA}_HOME, XDG_RUNTIME_DIR, TMPDIR
#     (under $out), env -i so no session variables leak in;
#   - own D-Bus session bus (dbus-run-session);
#   - no network (unshare --net: only a down loopback);
#   - its own user, host and PID namespaces: the user is `guest` (a stand-in
#     /etc/passwd and /etc/group bound over the real ones, as root of an outer
#     user namespace, before dropping back to the real uid), the host name
#     `deusvult`, and only the stage's processes exist, so btop, the prompt,
#     fastfetch and eza show nothing of the machine's owner;
#   - two nested Hyprland instances, the outer one a window on the host, the
#     inner one at exactly ${W}x${H}, which grim captures (never the host);
#   - the given theme folder (its .git left out), applied as
#     `omarchy theme set` stages it, TZ=UTC, the stock shell.json with the
#     weather widget off (there is no network for it).
# $root is removed unless KEEP=1.
#
#   tools/stage-preview.sh build/deus-vult-green-screen   # writes its preview.png
# Knobs (environment):
#   OUT        work dir, default /tmp/dv-preview; keep it short (the nested
#              Hyprland's sockets live under it, 108-byte socket paths)
#   ANSI       the terminal colour nearest the phosphor (green, yellow, white,
#              blue) for the prompt and fastfetch; tools/build.py sets it
#   WALLPAPER  file in backgrounds/, default 1-cross.png
#   DEST       where the preview goes, default <theme folder>/preview.png
#   WIDTH, HEIGHT, SCALE  capture pixels and scale: default a 1920x1080
#              logical desktop at 2x, scaled to 2560x1440 like the stock ones
set -euo pipefail

out=${OUT:-/tmp/dv-preview}
OMARCHY_PATH=${OMARCHY_PATH:-/usr/share/omarchy}
theme=${THEME_NAME:-}  # the theme folder's name, as `omarchy theme set` knows it
wallpaper=${WALLPAPER:-1-cross.png}
W=${WIDTH:-3840} H=${HEIGHT:-2160} S=${SCALE:-2}

if [[ ${1:-} == --identity ]]; then
  # As root of an outer user namespace with its own mounts and host name:
  # put guest@deusvult in place, then become the real uid again for the rest.
  mount --bind "$2/etc/passwd" /etc/passwd
  mount --bind "$2/etc/group" /etc/group
  hostname deusvult
  exec unshare --map-user="$STAGE_UID" --map-group="$STAGE_GID" --net --pid --fork --kill-child --mount-proc -- \
    dbus-run-session -- bash "$2/stage.sh" --inner "$2"
fi

if [[ ${1:-} == --inner ]]; then
  root=$2
  pids=()
  log() { echo "stage: $*" >&2; }
  die() { log "FAIL $*"; exit 1; }
  # shellcheck disable=SC2329 # invoked by the EXIT trap
  cleanup() {
    local p
    for ((i = ${#pids[@]} - 1; i >= 0; i--)); do
      p=${pids[$i]}
      kill "$p" 2>/dev/null || true
    done
    for p in "${pids[@]}"; do wait "$p" 2>/dev/null || true; done
  }
  trap cleanup EXIT
  wait_for() { # <tries*0.25s> <cmd…>
    local n=$1; shift
    for _ in $(seq "$n"); do "$@" >/dev/null 2>&1 && return 0; sleep 0.25; done
    return 1
  }

  [[ $(id -un)@$(hostname) == guest@deusvult ]] || die "identity is $(id -un)@$(hostname)"

  # --- Theme: what `omarchy theme set` stages, without its app retints.
  cur="$HOME/.local/state/omarchy/current"
  mkdir -p "$cur"
  cp -r "$root/theme" "$cur/next-theme"
  omarchy-theme-set-templates >/dev/null 2>&1 || log "theme templates reported an error"
  mv "$cur/next-theme" "$cur/theme"
  echo "$theme" >"$cur/theme.name"
  ln -s "$cur/theme/backgrounds/$wallpaper" "$cur/background"

  # --- Bar: stock shell.json, weather off (no network).
  mkdir -p "$HOME/.config/omarchy"
  jq '
      .disabledPlugins = ((.disabledPlugins // []) + ["omarchy.weather"])
    | .bar.layout |= map_values(map(select((if type == "object" then .id else . end) != "omarchy.weather")))
  ' "$OMARCHY_PATH/config/omarchy/shell.json" >"$HOME/.config/omarchy/shell.json"

  # --- Apps: Omarchy's own foot and btop configs, reading the staged theme.
  mkdir -p "$HOME/.config/foot" "$HOME/.config/btop/themes"
  cp "$OMARCHY_PATH/config/foot/foot.ini" "$HOME/.config/foot/foot.ini"
  cp "$OMARCHY_PATH/config/btop/btop.conf" "$HOME/.config/btop/btop.conf"
  ln -snf "$cur/theme/btop.theme" "$HOME/.config/btop/themes/current.theme"

  # --- Compositors (see Omavisor's stage.sh): "outer" is one window on the
  # host and floats "inner" at exactly ${W}x${H}; grim captures inner.
  hypr_env=(LIBSEAT_BACKEND=seatd HYPRLAND_NO_SD_VARS=1 HYPRLAND_NO_SD_NOTIFY=1 HYPRLAND_NO_CRASHREPORTER=1)
  start_hypr() { # <name> <runtime dir> <parent wayland socket> <config>: sets <name>_sig and <name>_wl
    local name=$1 dir=$2 parent=$3 conf=$4 sock sig
    mkdir -p "$dir" && chmod 700 "$dir"
    env "${hypr_env[@]}" XDG_RUNTIME_DIR="$dir" WAYLAND_DISPLAY="$parent" \
      Hyprland -c "$conf" >"$root/hyprland-$name.log" 2>&1 &
    pids+=($!)
    wait_for 80 compgen -G "$dir/hypr/*/.socket.sock" || die "$name Hyprland did not start (see $root/hyprland-$name.log)"
    sock=$(compgen -G "$dir/hypr/*/.socket.sock" | head -1)
    sig=$(basename "$(dirname "$sock")")
    wait_for 40 env XDG_RUNTIME_DIR="$dir" HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl monitors || die "$name hyprctl not answering"
    printf -v "${name}_sig" %s "$sig"
    printf -v "${name}_wl" %s "$dir/$(cd "$dir" && compgen -G 'wayland-*' | grep -v lock | head -1)"
  }
  mkdir -p "$HOME/.config/hypr"
  common='dofile(os.getenv("OMARCHY_PATH") .. "/default/hypr/bootstrap.lua")
require("default.hypr.helpers")
require("default.hypr.looknfeel")'
  cat >"$HOME/.config/hypr/outer.lua" <<LUA
$common
hl.monitor({ output = "", mode = "preferred", position = "0x0", scale = 1 })
hl.config({ general = { border_size = 0, gaps_in = 0, gaps_out = 0 }, animations = { enabled = false },
  misc = { disable_watchdog_warning = true } })
o.window(".*", { float = true, size = { $W, $H }, move = { 0, 0 } })
LUA
  # The staged theme's generated hyprland.lua carries its border colours.
  cat >"$HOME/.config/hypr/inner.lua" <<LUA
$common
dofile("$cur/theme/hyprland.lua")
hl.monitor({ output = "", mode = "${W}x${H}", position = "0x0", scale = $S })
hl.config({ misc = { disable_watchdog_warning = true }, cursor = { invisible = true }, animations = { enabled = false } })
LUA
  # shellcheck disable=SC2153 # HOST_WAYLAND comes in through env -i
  start_hypr outer "$OUTER_RT" "$HOST_WAYLAND" "$HOME/.config/hypr/outer.lua"
  # shellcheck disable=SC2154 # set by start_hypr through printf -v
  start_hypr inner "$XDG_RUNTIME_DIR" "$outer_wl" "$HOME/.config/hypr/inner.lua"
  # shellcheck disable=SC2154
  export HYPRLAND_INSTANCE_SIGNATURE=$inner_sig WAYLAND_DISPLAY=$inner_wl
  export QT_QPA_PLATFORM=wayland XDG_CURRENT_DESKTOP=Hyprland XDG_SESSION_TYPE=wayland
  out_name=$(hyprctl monitors -j | jq -r '.[0].name')
  wait_for 40 bash -c "hyprctl monitors -j | jq -e '.[0].width == $W and .[0].height == $H'" ||
    die "inner output is not ${W}x${H}: $(hyprctl monitors -j | jq -c '[.[] | {name, width, height, scale}]')"
  [[ -z $(hyprctl configerrors) || $(hyprctl configerrors) == *"no errors"* ]] || log "config errors: $(hyprctl configerrors)"

  # --- The shell.
  quickshell -n -p "$OMARCHY_PATH/shell" >>"$root/shell.log" 2>&1 &
  pids+=($!)
  # shellcheck disable=SC2016 # expanded by the inner bash
  wait_for 80 bash -c '[[ $(omarchy-shell shell ping) == ok ]]' || die "shell did not start (see $root/shell.log)"
  lw=$((W / S)) lh=$((H / S))
  hyprctl dispatch "hl.dsp.cursor.move({ x = $((lw - 4)), y = $((lh - 4)) })" >/dev/null

  # --- Windows, opened one at a time so dwindle tiles them in order: the
  # demo shell on the left, btop top right, the source file bottom right.
  term() { # <n windows after> <command…>
    local n=$1; shift
    foot --working-directory="$HOME/deus-vult" "$@" >>"$root/foot.log" 2>&1 &
    pids+=($!)
    wait_for 40 bash -c "(( \$(hyprctl clients -j | jq length) >= $n ))" || die "window $n did not open (see $root/foot.log)"
    sleep 1
  }
  term 1 env DEMO="$root/demo/left" bash --rcfile "$root/demo/rc" -i
  term 2 btop
  term 3 env DEMO="$root/demo/right" bash --rcfile "$root/demo/rc" -i
  sleep 8 # btop's graphs fill in
  ps -eo args >"$root/ps.log"
  grim -o "$out_name" "$root/desktop.png"
  log "captured $(magick identify -format '%wx%h' "$root/desktop.png")"
  exit 0
fi

# The stage runs from a copy, so no process line names the checkout's path.
repo=$(git -C "$(dirname -- "$(realpath -- "$0")")" rev-parse --show-toplevel)
theme_dir=$(realpath -- "${1:?usage: stage-preview.sh <theme folder>}")
theme=$(basename -- "$theme_dir")
title=$(sed 's/-/ /g; s/\b./\u&/g' <<<"$theme")  # deus-vult-green-screen: Deus Vult Green Screen
dest=${DEST:-$theme_dir/preview.png}
ansi=${ANSI:-green}
case $ansi in
  green) sgr=32 ;; yellow) sgr=33 ;; blue) sgr=34 ;; white) sgr=37 ;;
  *) echo "stage: ANSI must be green, yellow, blue or white" >&2; exit 1 ;;
esac

for tool in Hyprland hyprctl grim quickshell omarchy-shell foot btop fastfetch bat eza jq magick dbus-run-session unshare git; do
  command -v "$tool" >/dev/null || { echo "stage: needs $tool" >&2; exit 1; }
done
[[ -n ${WAYLAND_DISPLAY:-} ]] || { echo "stage: run from a Wayland session (the nested Hyprland opens as a window)" >&2; exit 1; }
host_wayland=$WAYLAND_DISPLAY
[[ $host_wayland == /* ]] || host_wayland="$XDG_RUNTIME_DIR/$host_wayland"
[[ -f $theme_dir/backgrounds/$wallpaper ]] || { echo "stage: no wallpaper '$wallpaper' in $theme_dir/backgrounds" >&2; exit 1; }

root="$out/run"
rt="$out/r" ort="$out/o"
rm -rf "$root" "$rt" "$ort"
mkdir -p "$root/home" "$rt" "$ort" "$root/tmp" "$root/etc" "$root/demo" "$root/theme"
chmod 700 "$rt" "$ort"
tar -C "$theme_dir" --exclude=.git -c . | tar -C "$root/theme" -x
cp "$0" "$root/stage.sh"

uid=$(id -u) gid=$(id -g)
printf 'root:x:0:0::/root:/bin/bash\nguest:x:%s:%s:guest:%s:/bin/bash\nnobody:x:65534:65534::/:/usr/bin/nologin\n' \
  "$uid" "$gid" "$root/home" >"$root/etc/passwd"
printf 'root:x:0:\nguest:x:%s:\nnobody:x:65534:\n' "$gid" >"$root/etc/group"

# A demo repo of the theme, committed by the publisher, with one change.
demo_repo="$root/home/deus-vult"
mkdir -p "$demo_repo"
cp -r "$root/theme/." "$demo_repo/"
git_demo() {
  env -i PATH="$PATH" HOME="$root/home" GIT_CONFIG_NOSYSTEM=1 TZ=UTC \
    GIT_AUTHOR_NAME="Deus Vult Digital" GIT_AUTHOR_EMAIL="contact@deusvult.digital" \
    GIT_COMMITTER_NAME="Deus Vult Digital" GIT_COMMITTER_EMAIL="contact@deusvult.digital" \
    GIT_AUTHOR_DATE="1984-11-09T12:00:00Z" GIT_COMMITTER_DATE="1984-11-09T12:00:00Z" \
    git -C "$demo_repo" "$@" >/dev/null
}
git_demo init -q -b main
git_demo add -A
git_demo commit -q -m "Every square pixel"
dim=$(omarchy-theme-color --file "$demo_repo/colors.toml" dark_foreground)
sed -i "s/^muted = .*/muted = \"$dim\"/" "$demo_repo/colors.toml"

# Fastfetch: the cross as its logo, and only what any Omarchy box shows.
cross=$(sed -n '/^CROSS = \[/,/^\]/p' "$repo/tools/make-backgrounds.py" | grep -o '"[.#]*"' | tr -d '"' |
  sed 's/#/██/g; s/\./  /g; s/^/$1/')
mkdir -p "$root/home/.config/fastfetch"
printf '%s\n' "$cross" >"$root/home/.config/fastfetch/cross.txt"
cat >"$root/home/.config/fastfetch/config.jsonc" <<JSON
{
  "logo": { "type": "file", "source": "~/.config/fastfetch/cross.txt", "color": { "1": "$ansi" }, "padding": { "top": 1, "right": 4 } },
  "display": { "separator": "  ", "key": { "width": 10 }, "color": { "keys": "$ansi", "title": "bright_$ansi" } },
  "modules": [
    "title", "separator",
    "os", "kernel", { "type": "wm", "key": "WM" },
    { "type": "custom", "key": "Theme", "format": "$title" },
    "terminal", { "type": "terminalfont", "key": "Font" }, "shell", "memory",
    { "type": "custom", "key": "Motto", "format": "EVERY SQUARE PIXEL" },
    "break", "colors"
  ]
}
JSON

# The demo shells: echo each command after the prompt, run it, then stay
# interactive at the same prompt.
printf 'PROMPT_SGR=%s\n' "$sgr" >"$root/demo/rc"
cat >>"$root/demo/rc" <<'RC'
PS1='\[\e[1;'"$PROMPT_SGR"'m\]guest@deusvult\[\e[0m\]:\[\e[34m\]\w\[\e[0m\]$ '
export LS_COLORS= EZA_COLORS= BAT_THEME=ansi GIT_PAGER=cat PAGER=cat
while IFS= read -r line; do
  printf '%s%s\n' "${PS1@P}" "$line"
  eval "$line" </dev/null
done <"$DEMO"
RC
cat >"$root/demo/left" <<'CMDS'
fastfetch
git log --oneline
git diff
eza --icons --tree --level 2 --group-directories-first backgrounds
CMDS
cat >"$root/demo/right" <<'CMDS'
bat --style=numbers --line-range 1:26 colors.toml
CMDS

# shellcheck disable=SC2329 # invoked by the EXIT trap
cleanup() {
  if [[ ${KEEP:-} == 1 ]]; then echo "stage: kept $root $rt $ort"; else rm -rf "$root" "$rt" "$ort"; fi
}
trap cleanup EXIT
set +e
env -i PATH=/usr/local/bin:/usr/bin:/usr/sbin OMARCHY_PATH="$OMARCHY_PATH" LANG=C.UTF-8 TZ=UTC TERM=dumb \
  GIO_USE_VFS=local GVFS_DISABLE_FUSE=1 \
  HOME="$root/home" XDG_RUNTIME_DIR="$rt" OUTER_RT="$ort" TMPDIR="$root/tmp" \
  XDG_CONFIG_HOME="$root/home/.config" XDG_STATE_HOME="$root/home/.local/state" \
  XDG_CACHE_HOME="$root/home/.cache" XDG_DATA_HOME="$root/home/.local/share" \
  HOST_WAYLAND="$host_wayland" WIDTH="$W" HEIGHT="$H" SCALE="$S" WALLPAPER="$wallpaper" THEME_NAME="$theme" \
  STAGE_UID="$uid" STAGE_GID="$gid" \
  unshare --map-root-user --mount --uts -- bash "$root/stage.sh" --identity "$root"
status=$?
set -e
if [[ $status == 0 ]]; then
  magick "$root/desktop.png" -resize 2560x1440 -strip "$dest"
  echo "stage: $dest $(magick identify -format '%wx%h' "$dest")"
else
  mkdir -p "$out/logs" && cp "$root"/*.log "$out/logs/" 2>/dev/null || true
fi
exit $status
