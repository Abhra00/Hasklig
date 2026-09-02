#!/usr/bin/env python3
import argparse
import glob
import os
import re
import shutil
from fontTools.ttLib import TTFont

# Weight definitions matching Adobe Source Code Pro specifications
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
    help="Path to input directory containing .otf/.ttf fonts",
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
    """Sets standard Windows and Macintosh name table entries."""
    name_tbl.setName(string_val, name_id, 3, 1, 0x0409)
    name_tbl.setName(string_val, name_id, 1, 0, 0)


def extract_base_family(font):
    """Extracts the base family name (e.g., 'Hasklig') from existing records."""
    name_tbl = font.get("name")
    if not name_tbl:
        return "Hasklig"

    # 1. Check Preferred/Typographic Family (ID 16)
    typo_family = name_tbl.getDebugName(16)
    if typo_family:
        return typo_family.strip()

    # 2. Check Family Name (ID 1) and strip weight suffixes
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

    # 1. Enforce Adobe Source Code Pro Dual-Naming Structure
    if "name" in font:
        name_tbl = font["name"]

        # Strip whitespace on existing records
        for rec in name_tbl.names:
            text = rec.toUnicode()
            if text != text.strip():
                name_tbl.setName(
                    text.strip(), rec.nameID, rec.platformID, rec.platEncID, rec.langID
                )
                modified = True

        if is_ribbi:
            # RIBBI (400 Regular, 700 Bold): ID 1/2 handled standardly; ID 16/17 omitted
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

            # Adobe explicitly omits Name ID 16/17 on RIBBI styles
            if name_tbl.getDebugName(16) or name_tbl.getDebugName(17):
                name_tbl.names = [
                    r for r in name_tbl.names if r.nameID not in (16, 17)
                ]
                modified = True
        else:
            # Non-RIBBI (200, 300, 500, 600, 900): Split into individual ID 1 families
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

    # 2. Sync CFF Top-Dict Weight String
    if "CFF " in font:
        top = font["CFF "].cff[font["CFF "].cff.fontNames[0]]
        expected_cff_weight = spec["cff"]
        if getattr(top, "Weight", None) != expected_cff_weight:
            top.Weight = expected_cff_weight
            modified = True

    # 3. Sync 'head' fontRevision with Name Table ID 5
    if "head" in font and "name" in font:
        ver_text = font["name"].getDebugName(5)
        if ver_text:
            rev_float = parse_float_version(ver_text)
            if rev_float is not None and round(font["head"].fontRevision, 3) != round(
                rev_float, 3
            ):
                font["head"].fontRevision = rev_float
                modified = True

    # 4. Fix Timestamp Inversion
    if "head" in font:
        head = font["head"]
        if head.created > head.modified:
            head.created, head.modified = head.modified, head.created
            modified = True

    # 5. Sync OS/2 fsSelection Flags
    new_sel = os2.fsSelection
    new_sel &= ~(1 << 5)  # Clear BOLD
    new_sel &= ~(1 << 6)  # Clear REGULAR

    # Set BOLD bit ONLY for Weight 700 (Bold)
    if weight == 700:
        new_sel |= 1 << 5

    # Set REGULAR bit for all upright styles (Name ID 2 == "Regular")
    if not is_italic:
        new_sel |= 1 << 6

    # Enable USE_TYPO_METRICS (bit 7)
    new_sel |= 1 << 7

    if new_sel != os2.fsSelection:
        os2.fsSelection = new_sel
        modified = True

    # 6. Prevent Clipping (Expand usWinAscent/Descent to fit yMax/yMin)
    if "head" in font:
        y_max = font["head"].yMax
        y_min = abs(font["head"].yMin)
        if os2.usWinAscent < y_max:
            os2.usWinAscent = y_max
            modified = True
        if os2.usWinDescent < y_min:
            os2.usWinDescent = y_min
            modified = True

    return modified


# Batch Process Fonts
font_files = sorted(
    glob.glob(os.path.join(SRC_DIR, "*.otf"))
    + glob.glob(os.path.join(SRC_DIR, "*.ttf"))
)

if not font_files:
    print(f"No .otf or .ttf fonts found in: {SRC_DIR}")
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
