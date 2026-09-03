#!/usr/bin/env python3
import argparse
import glob
import os
from fontTools.ttLib import TTFont

WEIGHT_NAMES = {200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
                600: "Semibold", 700: "Bold", 900: "Black"}
PS_INFIX = {200: "ExtraLight", 300: "Light", 400: "", 500: "Medium",
            600: "Semibold", 700: "Bold", 900: "Black"}

parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", default=".")
parser.add_argument("-o", "--output", default="./fixed")
parser.add_argument("--family", default="Hasklig")
args = parser.parse_args()

SRC_DIR = os.path.abspath(args.input)
OUT_DIR = os.path.abspath(args.output)
os.makedirs(OUT_DIR, exist_ok=True)


def set_name(name_tbl, name_id, value):
    name_tbl.setName(value, name_id, 3, 1, 0x0409)
    name_tbl.setName(value, name_id, 1, 0, 0)


def remove_name(name_tbl, name_id):
    name_tbl.names = [r for r in name_tbl.names if r.nameID != name_id]


def postscript_name(base_family, weight, is_italic):
    ps_family = base_family.replace(" ", "")
    if weight == 400:
        return f"{ps_family}-It" if is_italic else f"{ps_family}-Regular"
    infix = PS_INFIX.get(weight, "")
    return f"{ps_family}-{infix}It" if is_italic else f"{ps_family}-{infix}"


def sanitize(font, base_family):
    if "OS/2" not in font or "name" not in font or "head" not in font:
        return None

    os2 = font["OS/2"]
    head = font["head"]
    name_tbl = font["name"]

    weight = os2.usWeightClass
    is_italic = bool(os2.fsSelection & 0x01)
    is_ribbi = weight in (400, 700)
    weight_name = WEIGHT_NAMES.get(weight, "Regular")
    ps_name = postscript_name(base_family, weight, is_italic)

    if is_ribbi:
        subfamily = ("Bold Italic" if is_italic else "Bold") if weight == 700 \
            else ("Italic" if is_italic else "Regular")
        family = base_family
        full = base_family if subfamily == "Regular" else f"{base_family} {subfamily}"

        set_name(name_tbl, 1, family)
        set_name(name_tbl, 2, subfamily)
        set_name(name_tbl, 4, full)
        set_name(name_tbl, 6, ps_name)
        remove_name(name_tbl, 16)
        remove_name(name_tbl, 17)
    else:
        subfamily = "Italic" if is_italic else "Regular"
        family = f"{base_family} {weight_name}"
        typo_subfamily = f"{weight_name} Italic" if is_italic else weight_name
        full = f"{base_family} {typo_subfamily}"

        set_name(name_tbl, 1, family)
        set_name(name_tbl, 2, subfamily)
        set_name(name_tbl, 4, full)
        set_name(name_tbl, 6, ps_name)
        set_name(name_tbl, 16, base_family)
        set_name(name_tbl, 17, typo_subfamily)

    vendor_id = os2.achVendID.strip() if os2.achVendID else "NONE"
    set_name(name_tbl, 3, f"{head.fontRevision:.3f};{vendor_id};{ps_name};ADOBE")

    new_sel = os2.fsSelection
    new_sel &= ~((1 << 5) | (1 << 6) | (1 << 0))
    if is_italic:
        new_sel |= 1 << 0
    if weight == 700:
        new_sel |= 1 << 5
    if weight == 400 and not is_italic:
        new_sel |= 1 << 6
    os2.fsSelection = new_sel

    if os2.version < 4:
        os2.version = 4

    mac_style = head.macStyle & ~0b11
    if weight == 700:
        mac_style |= 0b01
    if is_italic:
        mac_style |= 0b10
    head.macStyle = mac_style

    if "CFF " in font:
        cff = font["CFF "].cff
        if cff.fontNames[0] != ps_name:
            cff.fontNames[0] = ps_name
        top = cff[cff.fontNames[0]]
        top.FamilyName = family
        top.FullName = full
        top.Weight = weight_name

    return ps_name


font_files = sorted(glob.glob(os.path.join(SRC_DIR, "*.otf")))

if not font_files:
    print(f"No .otf fonts found in: {SRC_DIR}")
else:
    for path in font_files:
        fn = os.path.basename(path)
        font = TTFont(path)
        ps_name = sanitize(font, args.family)
        if ps_name is None:
            print(f"Skipped: {fn}")
            font.close()
            continue
        out_path = os.path.join(OUT_DIR, f"{ps_name}.otf")
        font.save(out_path)
        print(f"{fn} -> {os.path.basename(out_path)}")
        font.close()

    print(f"\nDone. Saved to: {OUT_DIR}")
