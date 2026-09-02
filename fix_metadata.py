#!/usr/bin/env python3
import argparse
import glob
import os
import re
import shutil
from fontTools.ttLib import TTFont

WEIGHT_SPECS = {
    200: {"name": "ExtraLight", "cff": "Extra-light"},
    300: {"name": "Light",      "cff": "Light"},
    400: {"name": "Regular",    "cff": "Regular"},
    500: {"name": "Medium",     "cff": "Medium"},
    600: {"name": "Semibold",   "cff": "Semibold"},
    700: {"name": "Bold",       "cff": "Bold"},
    900: {"name": "Black",      "cff": "Black"},
}

parser = argparse.ArgumentParser(
    description="Sanitize font metadata strictly following Adobe Source Code Pro naming standards."
)
parser.add_argument(
    "-i",
    "--input",
    default=".",
    help="Path to input directory containing .otf fonts",
)
parser.add_argument(
    "-o",
    "--output",
    default="./fixed",
    help="Path to save sanitized fonts",
)
args = parser.parse_args()

SRC_DIR = os.path.abspath(args.input)
OUT_DIR = os.path.abspath(args.output)
os.makedirs(OUT_DIR, exist_ok=True)


def parse_float_version(ver_str):
    if not ver_str:
        return None
    match = re.search(r"(\d+\.\d+)", ver_str)
    return float(match.group(1)) if match else None


def set_name_records(name_tbl, name_id, string_val):
    name_tbl.setName(string_val, name_id, 3, 1, 0x0409)
    name_tbl.setName(string_val, name_id, 1, 0, 0)


def extract_base_family(font):
    name_tbl = font.get("name")
    if not name_tbl:
        return "Hasklig"

    typo_family = name_tbl.getDebugName(16)
    if typo_family:
        return typo_family.strip()

    fam = name_tbl.getDebugName(1)
    if fam:
        fam = fam.strip()
        for spec in WEIGHT_SPECS.values():
            w_name = spec["name"]
            if fam.endswith(" " + w_name):
                return fam[: -len(w_name)].strip()
        return fam

    return "Hasklig"


def sanitize_metadata(font):
    modified = False

    if "OS/2" not in font:
        return False

    os2 = font["OS/2"]
    weight = os2.usWeightClass
    spec = WEIGHT_SPECS.get(weight, {"name": "Regular", "cff": "Regular"})

    is_italic = bool(os2.fsSelection & 0x01)
    is_ribbi = weight in (400, 700)
    weight_name = spec["name"]
    base_family = extract_base_family(font)

    if "name" in font:
        name_tbl = font["name"]

        for rec in name_tbl.names:
            text = rec.toUnicode()
            if text != text.strip():
                name_tbl.setName(
                    text.strip(), rec.nameID, rec.platformID, rec.platEncID, rec.langID
                )
                modified = True

        if is_ribbi:
            subfamily = (
                "Bold Italic"
                if (weight == 700 and is_italic)
                else "Bold"
                if weight == 700
                else "Italic"
                if is_italic
                else "Regular"
            )
            full_name = f"{base_family} {subfamily}"

            set_name_records(name_tbl, 1, base_family)
            set_name_records(name_tbl, 2, subfamily)
            set_name_records(name_tbl, 4, full_name)

            if name_tbl.getDebugName(16) or name_tbl.getDebugName(17):
                name_tbl.names = [
                    r for r in name_tbl.names if r.nameID not in (16, 17)
                ]
                modified = True
        else:
            family_name = f"{base_family} {weight_name}"
            subfamily = "Italic" if is_italic else "Regular"
            typo_subfamily = f"{weight_name} Italic" if is_italic else weight_name
            full_name = f"{base_family} {typo_subfamily}"

            set_name_records(name_tbl, 1, family_name)
            set_name_records(name_tbl, 2, subfamily)
            set_name_records(name_tbl, 16, base_family)
            set_name_records(name_tbl, 17, typo_subfamily)
            set_name_records(name_tbl, 4, full_name)

        modified = True

    if "CFF " in font:
        top = font["CFF "].cff[font["CFF "].cff.fontNames[0]]
        expected_cff_weight = spec["cff"]
        if getattr(top, "Weight", None) != expected_cff_weight:
            top.Weight = expected_cff_weight
            modified = True

    if "head" in font and "name" in font:
        ver_text = font["name"].getDebugName(5)
        if ver_text:
            rev_float = parse_float_version(ver_text)
            if rev_float is not None and round(font["head"].fontRevision, 3) != round(
                rev_float, 3
            ):
                font["head"].fontRevision = rev_float
                modified = True

    if "head" in font:
        head = font["head"]
        if head.created > head.modified:
            head.created, head.modified = head.modified, head.created
            modified = True

    new_sel = os2.fsSelection
    new_sel &= ~(1 << 5)
    new_sel &= ~(1 << 6)

    if weight == 700:
        new_sel |= 1 << 5

    if not is_italic:
        new_sel |= 1 << 6

    new_sel |= 1 << 7

    if new_sel != os2.fsSelection:
        os2.fsSelection = new_sel
        modified = True

    return modified


font_files = sorted(glob.glob(os.path.join(SRC_DIR, "*.otf")))

if not font_files:
    print(f"No .otf fonts found in: {SRC_DIR}")
else:
    for path in font_files:
        fn = os.path.basename(path)
        font = TTFont(path)

        if sanitize_metadata(font):
            font.save(os.path.join(OUT_DIR, fn))
            print(f"Updated metadata: {fn}")
        else:
            shutil.copy(path, os.path.join(OUT_DIR, fn))
            print(f"Unchanged: {fn}")
        font.close()

    print(f"\nDone! Processed fonts saved to: {OUT_DIR}")
