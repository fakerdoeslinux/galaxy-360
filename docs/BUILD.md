# Building galaxy-360

## What the build box needs

| | |
|---|---|
| OS | Windows 10 or 11, x64 |
| SDK | Xbox 360 SDK **2.0.21256.3** or newer, installed to a path without spaces |
| Compiler | the SDK's `cl.exe` (PowerPC/Xenon target) — Visual Studio 2010's toolset is what the SDK ships against |
| CMake | 3.22 or newer |
| Python | 3.9+ (packaging only) |

The SDK is the only practical route: the console's **D3D9, XAudio2 and XInput** are the SDK's PowerPC libraries. The free
cross toolchains (libxenon and friends) ship no D3D9, so the whole renderer would have to be rewritten against raw Xenos
command buffers — that is not what this port does.

`XEDK` must point at the SDK root, the folder that holds `bin/win32` and `include/xbox360`. Check it before building:

```powershell
python tools\check-sdk.py
```

It reports the SDK version, the Xenon headers, the link libraries, and whether the patches are applied.

## 1. The tree

The port is a patch on top of Nebula. Its two patches apply in order at commit `4f40d95`:

```powershell
git clone https://github.com/keepvaibin/nebula nebula
cd nebula
git checkout 4f40d95

git apply ..\galaxy-360\patches\0001-linux-port.patch      # shared desktop port (menu, sounds, FPS row)
git apply ..\galaxy-360\patches\0002-xbox360-platform.patch # platform/xbox360 + the host's boot guard
```

`0001` is the same patch the Linux build uses, so one checkout serves both targets. `0002` adds `platform/xbox360/` and
one `#if defined(NEBULA_XBOX360)` block in `native/host/host_main.cpp`.

## 2. Configure

```powershell
$env:XEDK = "C:\Xbox360\SDK"
cmake -S platform/xbox360 -B build/x360 `
      -DCMAKE_TOOLCHAIN_FILE=platform/xbox360/toolchain-xbox360.cmake `
      -DNEBULA_X360_RENDERER=ON `
      -DNEBULA_RELEASE=ON
```

- `NEBULA_X360_RENDERER=ON` builds the title. Without it the configuration builds the platform layer and the runtime
  subset as static libraries — useful while the renderer core is in progress.
- `NEBULA_RELEASE=ON` leaves the test hooks out (the `GALAXY_TEST_*` variables and the frame telemetry). Ship with it on;
  the debug builds are slower by a few percent and write more to the log.
- `NEBULA_ARCHIVE_SOURCES` points at the vendored `third_party/archive` folder; if it is missing, the mod importer is left
  out and mods from archives will not load.

## 3. Build

```powershell
cmake --build build/x360 --config Release
```

Output: `build/x360/Release/nebula_x360.xex` and the game module beside it.

## 4. Package

```powershell
python scripts\package.py --build build\x360 --out dist\galaxy-360
```

That assembles the folder the console boots: `default.xex`, `data\`, `save\`, `mods\`, `programs.xsh` (when the shader
cook has run), plus `cover.png` for Aurora. See [RGH.md](RGH.md) for the copy.

## What the errors mean

| Message | Cause |
|---|---|
| `Set XEDK to the Xbox 360 SDK's root` | `XEDK` is unset, or points at a folder with no `bin/win32` |
| `Nothing here compiles on a desktop compiler` | CMake picked the host toolset: `-DCMAKE_TOOLCHAIN_FILE` was not passed |
| `no device at 1280x720` in `nebula.log` | the console refused the mode — usually a title started without a display, or a 4:3 panel with the dashboard's aspect forced |
| `the game module's API version differs` | host and game module were built from different trees; rebuild both |
| link: `unresolved external XAudio2Create` | `xaudio2.lib` missing from the link: the SDK install is incomplete |

## Building on Linux

Not the supported path for a title, for the reason above (no D3D9). What *does* build on Linux is the desktop port
(`nebula-linux`), which is where the game logic and the renderer's shared core are developed. Cross-building the console
title from Linux with a PowerPC clang and the SDK's headers is possible in principle; nothing in this tree has tried it,
so it is not documented as working.
