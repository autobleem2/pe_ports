"""Writes the synthetic Mega Drive ROMs of the BlastEm load test: a valid header, the reset vector pointing at an
endless `bra.s *` loop, zero padding to the given size. No game data - generated here, free to use anywhere.

usage: python mkrom.py OUT SIZE_KIB [smd|zip]
  (none)  a plain ROM of SIZE_KIB
  smd     the same ROM in the Super Magic Drive format (512-byte header, 16 KB blocks, each block's even and odd
          bytes split into its two halves; 1024 KB and over takes the grow step of load_smd_rom) - load_smd_rom in BlastEm's system.c
  zip     the plain ROM inside a .zip (zip.c's own buffer)
"""
import os
import struct
import sys
import zipfile


def make_rom(size):
    rom = bytearray(size)
    struct.pack_into(">II", rom, 0, 0x00FFFE00, 0x00000200)  # initial SSP, reset PC
    for v in range(2, 64):  # every other vector -> the same loop
        struct.pack_into(">I", rom, v * 4, 0x00000200)
    rom[0x100:0x110] = b"SEGA MEGA DRIVE "
    rom[0x120:0x150] = b"AB LOAD TEST".ljust(48)
    rom[0x150:0x180] = b"AB LOAD TEST".ljust(48)
    rom[0x180:0x18E] = b"GM 00000000-00"
    struct.pack_into(">II", rom, 0x1A0, 0, size - 1)  # ROM start/end
    struct.pack_into(">II", rom, 0x1A8, 0xFF0000, 0xFFFFFF)  # RAM start/end
    rom[0x1F0:0x1F3] = b"JUE"
    struct.pack_into(">H", rom, 0x200, 0x60FE)  # bra.s * (loop forever)
    return bytes(rom)


def to_smd(rom):
    out = bytearray(512)
    out[1], out[8], out[9] = 0x03, 0xAA, 0xBB  # is_smd_format: these bytes, bytes 3..7 zero, byte 2 zero
    for off in range(0, len(rom), 0x4000):
        block = rom[off:off + 0x4000]
        out += block[0::2] + block[1::2]  # first half: every word's first byte, second half: its second byte
    return bytes(out)


def main():
    out, kib = sys.argv[1], int(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else ""
    rom = make_rom(kib * 1024)
    if mode == "zip":
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("test%d.bin" % kib, rom)
    else:
        with open(out, "wb") as f:
            f.write(to_smd(rom) if mode == "smd" else rom)
    print(out)


if __name__ == "__main__":
    main()
