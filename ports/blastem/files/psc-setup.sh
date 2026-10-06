# BlastEm on the PlayStation Classic: sourced by launch.sh (port.ini, [launcher] pre=) in the App's folder, before the
# program starts. Licence: GPL-3.0-or-later, like the rest of this package.
#
#   roms/          the player's games (this package has none); BlastEm's Load ROM opens it first
#   .config/blastem/blastem.cfg
#                  the program's settings, made by the program itself the first time its menu changes one (until then
#                  it reads the default.cfg of this package). HOME is the App's folder.
#   .local/share/blastem/<game>/
#                  saved games and save states
mkdir -p roms .config/blastem .local/share/blastem
[ -f roms/README.txt ] || cp psc/roms-README.txt roms/README.txt
