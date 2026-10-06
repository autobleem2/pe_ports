# ioquake3 on the PlayStation Classic: sourced by launch.sh (port.ini, [launcher] pre=) in the App's folder, before
# the engine starts. Licence: GPL-2.0-or-later, like the rest of this package.
#
#   OA_DATA            where the "OpenArena data" App put the game files (baseoa/pak*.pk3); launch.sh hands it to
#                      the engine as fs_cdpath
#   .q3a/baseoa/psc_pad.cfg
#                      the key bindings of this run, made from files in psc/: the layout of the pad the App is run
#                      with (AB_APP_PAD_MODE: x360-kernel / x360 = an Xbox 360 pad, else the console's own pad) and,
#                      for the Xbox 360 layout, the style that suits player 1's pad - d-pad (left/right turn) for
#                      the console's own pad, which has no sticks, dual analog for any other pad. No answer from the
#                      pad daemon = dual analog. A file psc_extra.cfg in the App's folder is added at the end of
#                      psc_pad.cfg (the place for a player's own settings and for tests).
#
# The decision is logged in ioquake3-pad.log next to the engine's own log.

app=$(pwd -P)
OA_DATA=$(dirname "$app")/pe-openarena-data
export OA_DATA

padlog="${RUNTIME_LOG_PATH:-/tmp}/ioquake3-pad.log"
daemon_log="${AB_LOG_DIR:-/tmp/autobleem/logs}/abpadd.log"

# player 1's pad, as the pad daemon names it (it may still be starting: a few short waits)
player1=
tries=0
while [ "$tries" -lt 4 ]; do
    player1=$(grep 'abpadd: player 1 is ' "$daemon_log" 2>/dev/null | head -n 1)
    [ -n "$player1" ] && break
    tries=$((tries + 1))
    sleep 1
done

case "${AB_APP_PAD_MODE:-psc-kernel}" in
    x360-kernel|x360)
        layout=x360
        case "$player1" in
            *[Cc]lassic\ [Cc]ontroller*|*Sony\ Interactive*) style=dpad ;;
            *) style=analog ;;
        esac
        ;;
    *)
        layout=psc
        style=dpad
        ;;
esac

mkdir -p .q3a/baseoa
cfg=.q3a/baseoa/psc_pad.cfg
{
    cat psc/common.cfg
    if [ "$layout" = x360 ]; then
        cat "psc/pad-x360-$style.cfg"
    else
        cat psc/pad-psc.cfg
    fi
    [ -f psc_extra.cfg ] && cat psc_extra.cfg
} > "$cfg"

{
    echo "pad mode: ${AB_APP_PAD_MODE:-unset} -> layout $layout, style $style"
    echo "player 1: ${player1:-(no answer from the pad daemon)}"
    echo "data folder: $OA_DATA ($( [ -f "$OA_DATA/baseoa/pak0.pk3" ] && echo found || echo MISSING ))"
} > "$padlog" 2>&1
