#!/usr/bin/env python3
"""Lay out the folder the console boots: galaxy-360's packaging step.

    python3 scripts/package.py --xex build/x360/Release/nebula_x360.xex --out dist/galaxy-360 --data ~/nebula-data

Writes the layout docs/RGH.md describes — default.xex, the game's data, the shader cache when the cook has produced it,
empty save/ and mods/ folders, and the cover art — and a zip beside the folder. It runs anywhere Python does, because
packaging is file layout, not a build.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What a console title's folder holds. The names are the port's (platform_paths.h, xbox360_platform.cpp).
FOLDERS = ("save", "mods", "menu-sounds")

FOLDER_NOTE = """\
Copy this folder's contents to Hdd:\\Nebula\\ - it is the title's writable store.

  save\\          saves and the settings window's own state
  mods\\          mod packs, one folder or archive each
  menu-sounds\\   optional: focus.wav select.wav page.wav open.wav close.wav ok.wav

The title creates whatever is missing on first launch.
"""


def copy_tree(source: Path, target: Path) -> int:
    """Copies `source` into `target`, returning the number of files. Existing files are replaced; extras are kept."""
    count = 0
    for item in source.rglob("*"):
        if not item.is_file():
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Package galaxy-360 for a modded Xbox 360.")
    parser.add_argument("--xex", type=Path, help="the built nebula_x360.xex")
    parser.add_argument("--build", type=Path, help="alternatively, the build folder to find the .xex in")
    parser.add_argument("--out", type=Path, required=True, help="the output folder (dist/galaxy-360)")
    parser.add_argument("--data", type=Path, help="the cooked game data to copy into data/")
    parser.add_argument("--shaders", type=Path, help="programs.xsh (default: beside the .xex)")
    parser.add_argument("--no-zip", action="store_true", help="leave the folder unzipped")
    args = parser.parse_args()

    xex: Path | None = args.xex
    if xex is None:
        if args.build is None:
            parser.error("give --xex or --build")
        found = sorted(args.build.rglob("nebula_x360.xex"))
        if not found:
            print(f"no nebula_x360.xex under {args.build}: the renderer milestone is not built", file=sys.stderr)
            return 1
        xex = found[0]
    if not xex.is_file():
        print(f"no such file: {xex}", file=sys.stderr)
        return 1

    out = args.out
    if out.exists():
        shutil.rmtree(out)  # the folder is a build artefact: stale files in it are worse than a rebuild
    out.mkdir(parents=True)
    shutil.copy2(xex, out / "default.xex")

    shaders = args.shaders or (xex.parent / "programs.xsh")
    if shaders.is_file():
        shutil.copy2(shaders, out / "programs.xsh")
    else:
        print(f"warning: no {shaders.name}: a build without the cooked shader cache presents nothing", file=sys.stderr)

    data_files = 0
    if args.data is not None:
        if not args.data.is_dir():
            print(f"no such folder: {args.data}", file=sys.stderr)
            return 1
        data_files = copy_tree(args.data, out / "data")
    else:
        (out / "data").mkdir()
        print("warning: no --data: data/ is empty, and the title has nothing to boot", file=sys.stderr)

    # The title's writable store is Hdd:\Nebula (platform_paths.h), not the folder it boots from: ship it as a folder
    # to copy there, with the subfolders already made.
    store = out / "Hdd-Nebula"
    for name in FOLDERS:
        (store / name).mkdir(parents=True, exist_ok=True)
    (store / "README.txt").write_text(FOLDER_NOTE, encoding="utf-8")

    cover = ROOT / "assets" / "cover.png"
    if cover.is_file():
        shutil.copy2(cover, out / "cover.png")

    (out / "README.txt").write_text(
        "galaxy-360 - Super Mario Galaxy, native on the Xbox 360.\n"
        "\n"
        "Copy this folder to Hdd:\\Games\\Galaxy360\\ and launch default.xex from Aurora or FSD.\n"
        "Hold Start + Back for two seconds to exit. Saves and settings go to Hdd:\\Nebula\\.\n"
        "See docs/RGH.md in the project repository for the whole walk-through.\n",
        encoding="utf-8",
    )

    print(f"{out}: default.xex, {data_files} data files, Hdd-Nebula\\ to copy, "
          f"{'shaders' if (out / 'programs.xsh').is_file() else 'NO shaders'}")

    if not args.no_zip:
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for item in sorted(out.rglob("*")):
                if item.is_file():
                    bundle.write(item, item.relative_to(out.parent))
        print(f"{archive}: {archive.stat().st_size // (1024 * 1024)} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
