# LZDoom on the PlayStation Classic: sourced by launch.sh (port.ini, [launcher] pre=) in the App's folder, before
# the engine starts. Licence: GPL-3.0-only, like the rest of this package.
#
#   LZ_IWAD / LZ_MODS  what the engine plays: the game the launcher's "Choose game data" picked (AB_PKG_FILE, read-only:
#                      Freedoom from a package, or a WAD of this App's own WAD folder, which the launcher lists too).
#                      Without a pick - a launcher that has no game packages - the old search: the game file the
#                      player put in this App's WAD folder (Doom, Doom II,
#                      Heretic, ... anything *.wad there; the first by the order doom2, doom, plutonia, tnt, heretic,
#                      hexen, then by name), else Freedoom from the "Freedoom data" App (freedoom2.wad); every
#                      .wad/.pk3/.pk7/.zip in MODS is loaded as a mod (-file), by name. Names with spaces are skipped.
#   lzdoom.ini         the engine's settings file, in the App's folder: this script sets, every run, full screen and the
#                      pad's axes (section [Joy:JS:0]); the engine adds everything else it saves. The picture is the
#                      software renderer shown through SDL (the engine's default on ARM); vid_renderer=1 in the ini is the GL one.
#   psc_pad.cfg        the key bindings of this run, made from files in psc/: the layout of the pad the App is run
#                      with (AB_APP_PAD_MODE: x360-kernel / x360 = an Xbox 360 pad, else the console's own pad) and,
#                      for the Xbox 360 layout, the style that suits player 1's pad - d-pad for the console's own pad,
#                      dual analog for any other pad. No answer from the pad daemon = dual analog. A file
#                      psc_extra.cfg in the App's folder is added at the end of psc_pad.cfg (the place for a
#                      player's own settings and for tests).
#
# The decision is logged in lzdoom-pad.log next to the engine's own log.

app=$(pwd -P)
LZ_FREEDOOM=$(dirname "$app")/pe-freedoomdata
export LZ_FREEDOOM

padlog="${RUNTIME_LOG_PATH:-/tmp}/lzdoom-pad.log"
daemon_log="${AB_LOG_DIR:-/tmp/autobleem/logs}/abpadd.log"

# --- the game file and the mods ----------------------------------------------------------------------------
LZ_IWAD=
for name in doom2 doom plutonia tnt heretic hexen strife; do
    [ -n "${AB_PKG_FILE:-}" ] && break
    for f in WAD/"$name".wad WAD/"$name".WAD; do
        [ -f "$f" ] && { LZ_IWAD=$f; break 2; }
    done
done
if [ -z "$LZ_IWAD" ] && [ -z "${AB_PKG_FILE:-}" ]; then
    for f in WAD/*.wad WAD/*.WAD; do
        [ -f "$f" ] && { LZ_IWAD=$f; break; }
    done
fi
iwad_from="the WAD folder"
if [ -n "${AB_PKG_FILE:-}" ]; then
    LZ_IWAD=$AB_PKG_FILE
    iwad_from="game package ${AB_PKG_ID:-?}"
elif [ -z "$LZ_IWAD" ]; then
    LZ_IWAD=$LZ_FREEDOOM/freedoom2.wad
    iwad_from="Freedoom"
fi

LZ_MODS=
for f in MODS/*.wad MODS/*.WAD MODS/*.pk3 MODS/*.pk7 MODS/*.zip; do
    [ -f "$f" ] || continue
    case "$f" in *\ *) continue ;; esac
    LZ_MODS="$LZ_MODS $f"
done
[ -n "$LZ_MODS" ] && LZ_MODS="-file$LZ_MODS"
export LZ_IWAD LZ_MODS

# --- the pad -------------------------------------------------------------------------------------------------
player1=
case "${AB_APP_PAD_MODE:-psc-kernel}" in
    x360-kernel|x360)
        layout=x360
        # player 1's pad, as the pad daemon names it (it may still be starting: a few short waits)
        tries=0
        while [ "$tries" -lt 4 ]; do
            player1=$(grep 'abpadd: player 1 is ' "$daemon_log" 2>/dev/null | head -n 1)
            [ -n "$player1" ] && break
            tries=$((tries + 1))
            sleep 1
        done
        case "$player1" in
            *[Cc]lassic\ [Cc]ontroller*|*Sony\ Interactive*) style=dpad ;;
            *) style=analog ;;
        esac
        ;;
    *)
        # the console's own pad whatever is plugged in: nothing to choose
        layout=psc
        style=dpad
        ;;
esac

# the menus: Cross = OK, Circle = Back only for the console's own pad's order (Joy3 = Cross); the Xbox layout's A is Joy1
if [ "$layout" = psc ]; then LZ_MENUPAD=true; else LZ_MENUPAD=false; fi
export LZ_MENUPAD

{
    cat psc/common.cfg
    if [ "$layout" = x360 ]; then
        cat "psc/pad-x360-$style.cfg"
    else
        cat psc/pad-psc.cfg
    fi
    [ -f psc_extra.cfg ] && cat psc_extra.cfg
} > psc_pad.cfg

# axes of the joystick (EJoyAxis: -1 none, 0 yaw, 1 pitch, 2 forward, 3 side): the console's pad and the Xbox d-pad
# style use buttons only; the Xbox dual-analog style walks/strafes with the left stick and turns/looks with the right
if [ "$layout" = x360 ] && [ "$style" = analog ]; then
    axes="Axis0map=3 Axis1map=2 Axis2map=-1 Axis3map=0 Axis4map=1 Axis5map=-1"
else
    axes="Axis0map=-1 Axis1map=-1 Axis2map=-1 Axis3map=-1 Axis4map=-1 Axis5map=-1"
fi
mkdir -p saves
ini=lzdoom.ini
tmp=lzdoom.ini.new
# the ini is rewritten: the old [Joy:JS:0] section and the keys this script owns are dropped, then put back as wanted
if [ -f "$ini" ]; then
    awk '
        /^\[/ { sec = $0; if (sec == "[Joy:JS:0]") next }
        sec == "[Joy:JS:0]" { next }
        sec == "[GlobalSettings]" && /^(fullscreen)=/ { next }
        /^$/ { next }
        /^\[/ && NR > 1 { print "" }
        { print }
    ' "$ini" > "$tmp" 2>/dev/null || : > "$tmp"
else
    : > "$tmp"
fi
if grep -q '^\[GlobalSettings\]' "$tmp"; then
    awk '{ print } /^\[GlobalSettings\]/ { print "fullscreen=true" }' "$tmp" > "$ini"
else
    { printf '[GlobalSettings]\nfullscreen=true\n\n'; cat "$tmp"; } > "$ini"
fi
{
    echo
    echo "[Joy:JS:0]"
    for a in $axes; do echo "$a"; done
} >> "$ini"
rm -f "$tmp"

{
    echo "pad mode: ${AB_APP_PAD_MODE:-unset} -> layout $layout, style $style"
    echo "player 1: ${player1:-(no answer from the pad daemon)}"
    echo "game file: $LZ_IWAD (from $iwad_from; $( [ -f "$LZ_IWAD" ] && echo found || echo MISSING ))"
    echo "mods: ${LZ_MODS:-(none)}"
} > "$padlog" 2>&1
