# DOSBox on the PlayStation Classic: sourced by launch.sh (port.ini, [launcher] pre=) in the App's folder, before
# DOSBox starts. Licence: GPL-2.0-or-later, like the rest of this package.
#
# What the launcher hands over (packages spec, section 5.2; the launcher's picker has already chosen the game):
#   AB_PKG_DIR       the game package's folder: mounted as C: READ-WRITE (DOS games keep their saves and their
#                    SETUP's settings next to themselves; this is the one package an engine may write to)
#   AB_PKG_FILE      the game's main file (the one start when AB_PKG_STARTS is not set)
#   AB_PKG_TITLE     the game's name (the title of the choice screen)
#   AB_PKG_STARTS    "FILE|Title;FILE|Title": the programs that start the game (the game, its SETUP); the first is
#                    the default. Two or more: the choice screen (the 4 buttons of the PE dialog, at most 4 starts)
#   AB_PKG_SET_CYCLES / _MEMSIZE / _SOUND   the game's DOSBox settings (Game<N>.Dosbox.<name>):
#                    cycles = auto | max | a number | "fixed N" | "max N%" ...; memsize = 1..63 (MB);
#                    sound = sb16 | sbpro2 | sbpro1 | sb2 | sb1 | speaker (PC speaker only) | none
#   AB_PKG_MAPPER    the game's own pad map (a DOSBox mapper file); absent = mapper.txt of this App
# Without a launcher (a test, a stick without the new launcher) the folder is the script's argument or DB_PKG_DIR.
#
# What it makes, in the run's folder ($AB_RUNTIME_DIR/dosbox, RAM): dosbox.conf (the App's base settings, then the
# game's settings, the mapper's absolute path and the [autoexec] that mounts C: and runs the chosen program) and
# mapper.txt (a copy, so DOSBox never writes into the package). It sets DB_CONF for the command line of launch.sh.
#
#   DB_APP        this App's folder (default: the current folder; when run directly, the script's folder)
#   DB_RUN        the run's folder (default $AB_RUNTIME_DIR/dosbox, else /tmp/dosbox)
#   DB_CHOICE     1..4: take this start and skip the choice screen (tests)
# Run directly (sh psc-dosbox.sh [package folder]) it only prints what it made and what it would start.

db_standalone=0
case "$0" in
    psc-dosbox.sh | */psc-dosbox.sh)
        db_standalone=1
        DB_APP=${DB_APP:-$(cd "$(dirname "$0")" && pwd)}
        ;;
esac
DB_APP=${DB_APP:-$(pwd)}
DB_RUN=${DB_RUN:-${AB_RUNTIME_DIR:-/tmp}/dosbox}
db_log=${RUNTIME_LOG_PATH:-/tmp}/dosbox-start.log

db_die() {
    echo "dosbox: $*" >&2
    echo "dosbox: $*" >> "$db_log" 2> /dev/null
    printf 1 > /data/power/disable 2> /dev/null # launch.sh had set it to 2 (no sleep while a program runs)
    exit 1
}

db_pkg=${AB_PKG_DIR:-${DB_PKG_DIR:-$1}}
[ -n "$db_pkg" ] || db_die "no game package: AB_PKG_DIR is not set (start a DOS game from the Store's list)"
[ -d "$db_pkg" ] || db_die "the game package folder is gone: $db_pkg"
while [ "$db_pkg" != "/" ] && [ "${db_pkg%/}" != "$db_pkg" ]; do db_pkg=${db_pkg%/}; done
case "$db_pkg" in *'"'*) db_die "the package folder's name has a quote in it: $db_pkg" ;; esac

# --- the programs --------------------------------------------------------------------------------------------
db_list=$AB_PKG_STARTS
if [ -z "$db_list" ]; then
    db_one=$AB_PKG_FILE
    case "$db_one" in "$db_pkg"/*) db_one=${db_one#"$db_pkg"/} ;; esac
    [ -n "$db_one" ] || db_die "the game names no program to start"
    db_list="$db_one|${AB_PKG_TITLE:-Game}"
fi
db_old_ifs=$IFS
IFS=';'
set -f
set -- $db_list
set +f
IFS=$db_old_ifs
db_n=0
for db_entry in "$@"; do
    [ "$db_n" -lt 4 ] || break # the PE dialog answers with 4 buttons at most
    [ -n "$db_entry" ] || continue
    db_n=$((db_n + 1))
    db_file=${db_entry%%|*}
    case "$db_entry" in *'|'*) db_title=${db_entry#*|} ;; *) db_title=$db_file ;; esac
    # a path inside the package: relative, forward slashes, no way out
    case "$db_file" in
        '' | /* | .. | ../* | */.. | */../* | *\\*) db_die "the start program is not a path inside the package: $db_file" ;;
    esac
    eval "db_file_$db_n=\$db_file db_title_$db_n=\$db_title"
done
[ "$db_n" -ge 1 ] || db_die "the game names no program to start"

db_pick=1
if [ "$db_n" -ge 2 ]; then
    if [ -n "$DB_CHOICE" ]; then
        db_pick=$DB_CHOICE
    else
        db_text="${AB_PKG_TITLE:-DOSBox}\\n "
        db_i=1
        for db_button in Cross Circle Square Triangle; do
            [ "$db_i" -le "$db_n" ] || break
            eval "db_t=\$db_title_$db_i"
            db_text="$db_text\\n$db_button - $db_t"
            db_i=$((db_i + 1))
        done
        db_only=$(printf 'XOST' | cut -c1-"$db_n")
        "${PROJECT_ERIS_PATH:-/media/project_eris}/bin/sdl_input_text_display" "$db_text" 640 120 12 \
            /usr/share/fonts/ttf/LiberationMono-Regular.ttf 255 255 255 "$DB_APP/dosbox.png" "$db_only"
        db_rc=$?
        case "$db_rc" in
            100) db_pick=1 ;;
            101) db_pick=2 ;;
            102) db_pick=3 ;;
            103) db_pick=4 ;;
            *) echo "dosbox: the choice screen gave $db_rc - the first program" >> "$db_log" 2> /dev/null ;;
        esac
    fi
fi
case "$db_pick" in 1 | 2 | 3 | 4) ;; *) db_pick=1 ;; esac
[ "$db_pick" -le "$db_n" ] || db_pick=1
eval "db_prog=\$db_file_$db_pick"

# --- the run's folder: base settings + the game's -----------------------------------------------------------
mkdir -p "$DB_RUN" 2> /dev/null || db_die "cannot make the run's folder $DB_RUN"
[ -r "$DB_APP/dosbox.conf" ] || db_die "the base settings $DB_APP/dosbox.conf are missing"
db_conf=$DB_RUN/dosbox.conf
db_map=$DB_RUN/mapper.txt
cp "$DB_APP/dosbox.conf" "$db_conf" || db_die "cannot write $db_conf"
if [ -n "$AB_PKG_MAPPER" ] && [ -r "$AB_PKG_MAPPER" ]; then
    cp "$AB_PKG_MAPPER" "$db_map" || db_die "cannot write $db_map"
else
    [ -n "$AB_PKG_MAPPER" ] && echo "dosbox: the game's mapper file $AB_PKG_MAPPER is not readable - the default" >> "$db_log" 2> /dev/null
    cp "$DB_APP/mapper.txt" "$db_map" || db_die "cannot write $db_map"
fi

{
    echo ""
    echo "# --- this game ---"
    # a setting is passed on only in a shape DOSBox's own checks understand; anything else is left out and logged
    db_cycles=$AB_PKG_SET_CYCLES
    case "$db_cycles" in
        '') ;;
        *[!a-zA-Z0-9' '%]*) echo "# cycles: ignored (not a DOSBox value)" ;;
        *) printf '[cpu]\ncycles=%s\n' "$db_cycles" ;;
    esac
    db_mem=$AB_PKG_SET_MEMSIZE
    case "$db_mem" in
        '') ;;
        *[!0-9]*) echo "# memsize: ignored (not a number)" ;;
        *) if [ "$db_mem" -ge 1 ] && [ "$db_mem" -le 63 ]; then printf '[dosbox]\nmemsize=%s\n' "$db_mem"; else echo "# memsize: ignored (1..63)"; fi ;;
    esac
    case "$AB_PKG_SET_SOUND" in
        '') ;;
        sb16 | sbpro2 | sbpro1 | sb2 | sb1) printf '[sblaster]\nsbtype=%s\n' "$AB_PKG_SET_SOUND" ;;
        speaker) printf '[sblaster]\nsbtype=none\n[gus]\ngus=false\n[speaker]\npcspeaker=true\n' ;;
        none) printf '[mixer]\nnosound=true\n[sblaster]\nsbtype=none\n[speaker]\npcspeaker=false\n' ;;
        *) echo "# sound: ignored (sb16, sbpro2, sbpro1, sb2, sb1, speaker or none)" ;;
    esac
    printf '[sdl]\nmapperfile=%s\n' "$db_map"
    echo "[autoexec]"
    printf 'mount c "%s"\n' "$db_pkg"
    echo "c:"
    case "$db_prog" in
        */*)
            db_dir=$(printf '%s' "${db_prog%/*}" | tr '/' '\\')
            printf 'cd \\%s\n' "$db_dir"
            printf '%s\n' "${db_prog##*/}"
            ;;
        *) printf '%s\n' "$db_prog" ;;
    esac
    echo "exit"
} >> "$db_conf"

DB_CONF=$db_conf
export DB_CONF
echo "dosbox: $db_pkg, start $db_pick of $db_n ($db_prog), conf $db_conf" >> "$db_log" 2> /dev/null

if [ "$db_standalone" = 1 ]; then
    echo "conf: $db_conf"
    echo "mapper: $db_map"
    echo "start: $db_prog"
    exit 0
fi
