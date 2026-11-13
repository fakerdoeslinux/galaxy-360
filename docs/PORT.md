# The port

What `platform/xbox360/` puts under the game, file by file. Nebula splits cleanly: `runtime/` is the game's services and
renderer, `native/` is the decompiled game, and a platform supplies the window, the sound device, the clock and the
answers a desktop would give. That is the whole job here.

## The files

| File | What it does |
|---|---|
| `xbox360_platform.h/.cpp` | the machine: scaler mode at boot, memory report, the run's log, Xenon's clock, `pin_this_thread`, `shutdown` |
| `host_window_xbox360.cpp` | the "window": the device, its extent, present pacing, the pad exit chord, and the desktop-only questions the settings menu asks (monitors, pickers, upscalers) answered for a console |
| `xenos_device.h/.cpp` | the GPU: the D3D9 device, the multisampled target, predicated tiles, the resolve, texture creation and the tiling swizzle, `wait_idle` |
| `audio_device_xbox360.cpp` | XAudio2 at 48 kHz stereo, a four-block float ring the mixer fills from the voice's callbacks |
| `xbox360_tuning.h` | the console's numbers: 1280×720@60, the EDRAM tile, the memory split, the thread plan, streaming and the shader cache |
| `xbox360_apis.h` | the four SDK entry points that have no header of their own (`XGSwizzleRect`, `XGetVideoMode`, `XVideoSetMode`, `XSetThreadProcessor`, `XSetThreadName`) |
| `toolchain-xbox360.cmake` | the SDK's toolchain as CMake sees it |
| `CMakeLists.txt` | the platform library, the runtime subset, and the title |

## The seams, and what fills them

Nebula already declared where a platform plugs in. Four of those declarations are console-shaped:

```cpp
// runtime/include/galaxy/platform_time.h — the clock is Xenon's 50 MHz time base.
[[nodiscard]] inline std::uint64_t xbox360_time_base() noexcept;  // mftbu / mftb / mftbu

// runtime/include/galaxy/platform_paths.h — the writable store.
#elif defined(NEBULA_XBOX360)
    return std::filesystem::path("Hdd:\\Nebula");

// platform/xbox360/xbox360_tuning.h — the budgets, upstream's own.
inline constexpr int kFrameWidth = 1280;   // progressive, scaled by the GPU to the panel
inline constexpr std::uint32_t kUsableMemoryBytes = 480u * 1024u * 1024u;
```

Under those, the port implements the interfaces the runtime already calls:

- `galaxy::host::open_audio_device()` / `set_audio_thread_name()` — `audio_device_xbox360.cpp`
- `galaxy::render::host_window::*` — `host_window_xbox360.cpp` (the same set the Win32 and SDL hosts fill)
- `galaxy::host::x360::start()` / `machine()` / `open_log()` / `now_us()` / `shutdown()` — `xbox360_platform.cpp`
- `galaxy::host::x360::xenos()` — `xenos_device.cpp`, the device the renderer draws through

The host's `main()` gains one guarded block, next to the SDL one:

```cpp
#if defined(NEBULA_XBOX360)
    if (!galaxy::host::x360::start()) {
        return 1;   // no video mode: nothing to present into
    }
    galaxy::host::x360::open_log("Hdd:\\Nebula\\nebula.log");
#endif
```

## Boot order

1. `x360::start()` asks the scaler for 1280×720 progressive at 60 Hz, reads back the panel the dashboard is on, and logs
   memory, panel, aspect and interlacing. A title cannot change the panel; it renders into it.
2. The run's log opens at `Hdd:\Nebula\nebula.log`, appended. Every log line also goes to stderr, which is the console's
   debug channel — a debug monitor or XeLL reads it, so a session with nobody watching still leaves a trace.
3. `open_game_window` opens the Xenos device: 2× multisampled colour and depth, a resolve texture at 1280×720, and the
   device's own present.
4. The mixer opens XAudio2: mastering voice at 48 kHz stereo, one float source voice, four 512-frame blocks of ring.
5. Threads are pinned by the plan in `xbox360_tuning.h` — the game off the audio core, the renderer off the game's
   processors, core 0 thread 0 left to the kernel and the guide.

## The exit

There is no window to close. The console's own way out of a title is the guide, and its chord reaches the title as Start
and Back in the same poll: `host_window_xbox360.cpp` watches for two seconds of it and sets `quit_request`, which the host
already honours. `restart_game` does the same thing — a title restarts by exiting and being launched again.

## Deliberate omissions

- **No file pickers.** A console has none. `pick_files` returns nothing and `open_folder` does nothing; the package's own
  folder layout is the answer to "where are the mods".
- **No vendor upscalers.** No DLSS, no XeSS, no frame generation, and therefore no downloads and no licence dialogs.
  `upscaler_caps` reports one frame presented; the port's FSR 1 path is a shader and stays available.
- **No tray, no hidden start, no second monitor.** One panel, always on the screen.
- **No resolution list.** The mode is the console's; the settings menu shows the panel's size and rate and offers no
  other.
