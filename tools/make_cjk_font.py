#!/usr/bin/env python3
"""Builds the CJK fallback font (cjk.nft2) that Pico Launcher loads from the SD card.

The launcher's built-in fonts have no Chinese glyphs. When /_pico/fonts/cjk.nft2 exists,
the launcher draws every character the built-in font lacks with this font instead, so
Chinese file names and game titles show up.

The glyphs come from WenQuanYi Bitmap Song 12px (GPL v2 with a font embedding exception,
see licenses/wqy-bitmap-song.txt), a real pixel font that stays sharp at this size.
Only the GB2312 characters (simplified Chinese, CJK punctuation, fullwidth forms) are
written. Latin letters and digits keep using the built-in fonts.

Usage:
    make_cjk_font.py [--source wenquanyi_9pt.pcf.gz|.bdf] [--output cjk.nft2]
    make_cjk_font.py --check cjk.nft2

A .pcf source needs pcf2bdf (Debian/Ubuntu: apt install pcf2bdf xfonts-wqy).
"""

import argparse
import gzip
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

NFT2_SIGNATURE = 0x3254464E
HEADER_SIZE = 20
GLYPH_SIZE = 8
DEFAULT_SOURCES = [
    "/usr/share/fonts/X11/misc/wenquanyi_9pt.pcf",
    "/usr/share/fonts/X11/misc/wenquanyi_9pt.pcf.gz",
]
MIN_EXPECTED_CHARACTERS = 6000


def gb2312_characters():
    chars = set()
    for lead in range(0xA1, 0xF8):
        for trail in range(0xA1, 0xFF):
            try:
                chars.add(ord(bytes((lead, trail)).decode("gb2312")))
            except UnicodeDecodeError:
                pass
    # the ideographic space and the fullwidth forms GB2312 has no code for
    chars.add(0x3000)
    chars.update(range(0xFF01, 0xFF5F))
    return chars


def read_source(path):
    """Returns the text of a BDF font, converting a PCF (optionally gzipped) first."""
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if data.startswith(b"STARTFONT"):
        return data.decode("latin-1")
    if not shutil.which("pcf2bdf"):
        sys.exit("pcf2bdf is needed to read a PCF font (apt install pcf2bdf)")
    with tempfile.TemporaryDirectory() as tmp:
        pcf = Path(tmp) / "font.pcf"
        pcf.write_bytes(data)
        result = subprocess.run(["pcf2bdf", str(pcf)], check=True, capture_output=True)
        return result.stdout.decode("latin-1")


def parse_bdf(text):
    """Returns (ascent, descent, {codepoint: (dwidth, w, h, xoff, yoff, rows)})."""
    ascent = descent = None
    glyphs = {}
    lines = iter(text.splitlines())
    for line in lines:
        if line.startswith("FONT_ASCENT"):
            ascent = int(line.split()[1])
        elif line.startswith("FONT_DESCENT"):
            descent = int(line.split()[1])
        elif line.startswith("STARTCHAR"):
            code = dwidth = bbx = None
            rows = []
            for line in lines:
                if line.startswith("ENCODING"):
                    code = int(line.split()[1])
                elif line.startswith("DWIDTH"):
                    dwidth = int(line.split()[1])
                elif line.startswith("BBX"):
                    bbx = tuple(int(v) for v in line.split()[1:5])
                elif line.startswith("BITMAP"):
                    for line in lines:
                        if line.startswith("ENDCHAR"):
                            break
                        rows.append(int(line, 16) if line.strip() else 0)
                    break
            if code is not None and code >= 0 and bbx and dwidth is not None:
                w, h = bbx[0], bbx[1]
                row_bits = ((w + 7) // 8) * 8
                bitmap = [[(r >> (row_bits - 1 - x)) & 1 for x in range(w)] for r in rows[:h]]
                glyphs[code] = (dwidth, w, h, bbx[2], bbx[3], bitmap)
    if ascent is None or descent is None:
        sys.exit("the font has no FONT_ASCENT / FONT_DESCENT")
    return ascent, descent, glyphs


def build(ascent, descent, glyphs, wanted):
    # a character needs a glyph in the source; blank ones (spaces) are kept for their width
    codes = sorted(c for c in wanted if c in glyphs)
    table = bytearray()
    data = bytearray()
    # glyph 0 is the "missing" glyph: no pixels, no width, so a character
    # that maps to it falls through to the next font
    table += struct.pack("<IbbBb", 0, 0, 0, 0, 0)
    index = {}
    for code in codes:
        dwidth, w, h, xoff, yoff, rows = glyphs[code]
        index[code] = len(table) // GLYPH_SIZE
        offset = len(data)
        if offset >= 1 << 24 or w > 255:
            sys.exit("glyph data does not fit the NFT2 format")
        for row in rows:
            for x in range(0, w, 2):
                lo = 15 if row[x] else 0
                hi = 15 if x + 1 < w and row[x + 1] else 0
                data.append(lo | (hi << 4))
        top = ascent - (yoff + h)
        table += struct.pack("<IbbBb", offset | (w << 24), xoff, dwidth - xoff - w, h, top)

    # runs of consecutive characters; small gaps are bridged with the missing glyph
    charmap = bytearray()
    run_start, run = 0, []

    def flush():
        nonlocal charmap, run
        if run:
            charmap += struct.pack("<HH", len(run), run_start) + struct.pack("<%dH" % len(run), *run)
        run = []

    for code in codes:
        if run and code - (run_start + len(run)) > 8:
            flush()
        if not run:
            run_start = code
        run += [0] * (code - (run_start + len(run)))
        run.append(index[code])
    flush()
    charmap += struct.pack("<HH", 0, 0)

    glyph_off = HEADER_SIZE
    map_off = glyph_off + len(table)
    data_off = map_off + len(charmap)
    header = struct.pack("<IIIIBBH", NFT2_SIGNATURE, glyph_off, map_off, data_off,
                         ascent, descent, len(table) // GLYPH_SIZE)
    return header + table + charmap + data, len(codes)


def check(path):
    """Reads the font back the way the launcher does and returns how many characters it has."""
    blob = Path(path).read_bytes()
    sig, glyph_off, map_off, data_off, ascent, descent, count = struct.unpack_from("<IIIIBBH", blob)
    assert sig == NFT2_SIGNATURE, "bad signature"
    assert max(glyph_off, map_off, data_off) < len(blob), "table offset past the end"
    assert glyph_off + count * GLYPH_SIZE <= len(blob), "glyph table past the end"
    pos, chars = map_off, 0
    while True:
        n, start = struct.unpack_from("<HH", blob, pos)
        if n == 0:
            break
        for g in struct.unpack_from("<%dH" % n, blob, pos + 4):
            assert g < count, "glyph index out of range"
            chars += g != 0
        pos += 4 + 2 * n
    print(f"{path}: {len(blob):,} bytes, {count} glyphs, {chars} characters, "
          f"ascend {ascent}, descend {descent}")
    return chars


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="WenQuanYi 9pt bitmap font (.pcf, .pcf.gz or .bdf), default: the xfonts-wqy package")
    parser.add_argument("--output", default="cjk.nft2")
    parser.add_argument("--check", metavar="FONT", help="only verify an existing .nft2 file")
    args = parser.parse_args()
    if args.check:
        check(args.check)
        return

    source = args.source or next((p for p in DEFAULT_SOURCES if Path(p).exists()), None)
    if not source:
        sys.exit("no source font found, install xfonts-wqy or pass --source")
    ascent, descent, glyphs = parse_bdf(read_source(source))
    wanted = gb2312_characters()
    blob, count = build(ascent, descent, glyphs, wanted)
    missing = len([c for c in wanted if c not in glyphs])
    Path(args.output).write_bytes(blob)
    print(f"{count} characters written, {missing} of the {len(wanted)} wanted ones are not in the source")
    if check(args.output) < MIN_EXPECTED_CHARACTERS:
        sys.exit("far fewer characters than expected, is the source the WenQuanYi bitmap font?")


if __name__ == "__main__":
    main()
