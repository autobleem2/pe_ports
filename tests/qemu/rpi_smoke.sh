#!/bin/sh
# the Raspberry Pi 32-bit smoke test: tests/qemu/smoke.sh rpi (the target comes first there)
exec sh "$(dirname "$0")/smoke.sh" rpi "$@"
