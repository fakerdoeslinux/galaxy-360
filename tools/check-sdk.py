#!/usr/bin/env python3
"""Check a build box for the Xbox 360 SDK and the headers this port links against.

    python3 tools/check-sdk.py [--tree <nebula checkout>]

Exits 0 when everything a build needs is present, 1 otherwise. Read-only: it never writes to the SDK or the tree.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# What platform/xbox360 actually includes or links. A missing one is a hard stop: the SDK install is incomplete.
HEADERS = ("xtl.h", "xgraphics.h", "d3d9.h", "xaudio2.h", "xinput.h")
LIBS = ("d3d9.lib", "xgraphics.lib", "xaudio2.lib", "xinput.lib", "xapilib.lib")
TOOLS = ("bin/win32/cl.exe", "bin/win32/lib.exe")

PIN = "4f40d95"


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'ok  ' if ok else 'FAIL'}] {label}{': ' + detail if detail else ''}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Check for the Xbox 360 SDK this port builds against.")
    parser.add_argument("--tree", type=Path, help="a Nebula checkout, to check the port's patches are applied")
    args = parser.parse_args()

    good = True
    xedk_text = os.environ.get("XEDK", "")
    xedk = Path(xedk_text) if xedk_text else None
    good &= check("XEDK is set", xedk is not None, str(xedk) if xedk else "set it to the SDK's root")
    if xedk is None or not xedk.is_dir():
        print("\nnothing else can be checked without the SDK")
        return 1

    for tool in TOOLS:
        good &= check(tool, (xedk / tool).is_file())
    for header in HEADERS:
        path = xedk / "include" / "xbox360" / header
        good &= check(f"include/xbox360/{header}", path.is_file())

    lib_dir = xedk / "lib" / "xbox360"
    for lib in LIBS:
        good &= check(f"lib/xbox360/{lib}", (lib_dir / lib).is_file())

    version_file = xedk / "include" / "xbox360" / "xdkver.h"
    if version_file.is_file():
        text = version_file.read_text(errors="replace")
        found = re.findall(r"_XDK_VER\s+(0x[0-9a-fA-F]+)", text)
        if found:
            print(f"[info] SDK version {found[0]} (the port is written against 2.0.21256.3 or newer)")

    if args.tree is not None:
        tree = args.tree
        if not (tree / ".git").is_dir():
            good &= check("Nebula checkout", False, f"{tree} is not a git checkout")
        else:
            head = subprocess.run(["git", "-C", str(tree), "rev-parse", "--short", "HEAD"], capture_output=True,
                                  text=True).stdout.strip()
            check("Nebula commit", head == PIN, f"{head} (patches are cut against {PIN})")
            platform_dir = tree / "platform" / "xbox360"
            good &= check("platform/xbox360 present", (platform_dir / "xenos_device.cpp").is_file(),
                          "run patches/0002-xbox360-platform.patch")
            host_main = tree / "native" / "host" / "host_main.cpp"
            if host_main.is_file():
                good &= check("host boot guard", "NEBULA_XBOX360" in host_main.read_text(errors="replace"))

    print("\nready to build" if good else "\nsomething above is missing")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
