# Running it on an RGH or JTAG console

Nothing here is unusual for a homebrew title: a folder with `default.xex` in it, launched from a file manager. What
follows is the whole path from the build box to the TV.

## What you need

- A console with **RGH 1.x/3, RGH2, S-RGH, or JTAG** and a current **freeboot** image. Those run devkit-signed code,
  which is what an SDK build produces.
- A file manager: **Aurora**, **FSD 3 (Freestyle Dash)**, or anything else that launches a `.xex` from a path.
- A way to copy files: the console's **FTP server** (Aurora and FSD both have one), a FAT32 USB stick, or SMB if your
  dash supports it.

## 1. Copy the folder

Package on the build box (`python scripts\package.py --build build\x360 --out dist\galaxy-360`), then put the folder on
the console's hard disk:

```
Hdd:\Games\Galaxy360\        <- dist\galaxy-360
    default.xex
    cover.png
    data\            the game's own cooked data
    programs.xsh     the cooked shaders
    Hdd-Nebula\      <- copy the contents of this into Hdd:\Nebula\

Hdd:\Nebula\                  <- the title's writable store
    runtime_settings.ini
    nebula.log
    save\
    mods\
    menu-sounds\
```

Over FTP the same thing is one drag of the folder into `Hdd:\Games\`, then a drag of `Hdd-Nebula`'s contents into
`Hdd:\Nebula\`. If you use a USB stick, format it **FAT32** (the console reads nothing else) and copy the folder to the
root; the store still goes to `Hdd:\Nebula\`, so a stick-only console wants the store folder made by hand — the title
creates it if it is missing.

## 2. Launch it

In Aurora or FSD, browse to `Hdd:\Games\Galaxy360\default.xex` and press A. First launch takes a few seconds longer than
later ones: the shader cache is read and the save folder is created.

If the screen stays black, read `Hdd:\Nebula\nebula.log` over FTP. The first lines say what the console gave the title:

```
[x360] panel 1920x1080 60 Hz wide, 412 of 480 MB free, 6 hardware threads, video mode 1280x720@60
[xenos] device open: 1280x720, 2x multisample, predicated tiling on
[audio] XAudio2 ...
```

A missing `panel` line means the title never got a display (wrong boot path, or a dashboard setting that killed the
mode). A `no device at 1280x720` line means the console refused the mode.

## 3. Getting out

Hold **Start + Back** for two seconds. That is the guide's own chord; the title reads it as an exit request and shuts
down cleanly — the log is flushed and the scaler's mode is left as the dashboard had it. Do not power the console off
mid-game if you can avoid it: the save folder's writes are atomic, but a hard cut loses the session's settings.

## 4. Cover art

Aurora shows a cover for a title it can identify. Two ways:

- **By folder.** Drop `cover.png` beside `default.xex` — 1024×1024 or the case's ratio both work; the one in `assets/`.
- **By title ID.** Aurora keeps box art under `Aurora\Media\Covers\<TitleID>\cover.png`. Copy the same file there.

The cover in this repository is drawn by `assets/generate-art.py`: a nebula, a ringed planet, the wordmark. No Nintendo
artwork is redistributed, so if you want the retail box, that is yours to supply.

## 5. Saves and settings

- Saves are Nebula's own format, in `Hdd:\Nebula\save\`. They are the same files the desktop port writes, so a save can
  move between the two (copy `saves\` across; the format is identical).
- Settings live in `Hdd:\Nebula\runtime_settings.ini` and can be edited on the console over FTP. The F10 menu on desktop
  is the console's **Start** overlay: the same rows, the same values.
- The pause menu's sound effects come from the Wii's own clips when they are installed (`Hdd:\Nebula\menu-sounds\`);
  without them the game's own effects are used.

## 6. Updating

Replace `default.xex` and `data\`, keep `save\`, `mods\` and `Hdd:\Nebula\`. The save format is versioned and does not
move between builds of this port.

## Known limits

- **No measurements from this tree.** The platform layer was written without a console to run it on; the first thing to
  check on hardware is the log's boot line and whether the device opens at 2× MSAA. If the driver refuses multisampling at
  720p, drop `kMultisample` to 1 in `platform/xbox360/xbox360_tuning.h` — the resolve and tiling paths do not care.
- **A 4:3 panel** gets the same 1280×720 frame, letterboxed by the scaler. The HUD is laid out for 16:9; nothing in the
  port crops it.
- **No Xbox Live, no achievements.** A modded console runs no signed services for a homebrew title.
