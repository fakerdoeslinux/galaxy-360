# The console's budgets

A PC port spends what it finds. A console port spends what it was given, and the numbers below are the whole of it: a
16.67 ms frame, 480 MB of memory, ten megabytes of framebuffer, and one shader generation. Everything in this document is
either a constant of the machine or a decision in `platform/xbox360/xbox360_tuning.h`. Nothing here is a benchmark — no
console ran this tree; see the note at the bottom.

## One frame

| | ms |
|---|---|
| the game's step — simulation, physics, animation, records built | 10.5 |
| the renderer's submit — states, draws, the kick | 4.0 |
| audio, on its own thread | 0.8 |
| slack | 1.3 |
| **period at 60 Hz** | **16.67** |

The frame limiter targets 16 ms (`kFrameBudgetMs`) so a late frame is a single dropped vsync rather than two. The shape
matters more than the split: at 60 Hz there is no room for a 20 ms frame, so any work that can leave the frame thread
must — texture uploads, pak reads, the mix.

## Memory: 480 MB, sized once

The console has 512 MB. The hypervisor, kernel and the graphics driver keep about 32 MB of it; a title counts on 480 MB
and the dashboard's guide is not resident while a title runs.

```cpp
inline constexpr MemorySplit kMemory{192u, 128u, 48u, 36u, 68u, 4u, 4u};
//                                     pak  tex  geo  aud  heap  shdr spare
```

| Pool | MB | Why that size |
|---|---|---|
| pak stream | 192 | read-ahead plus the streaming ring: a level's textures and audio, with room for a transition |
| textures | 128 | GPU-visible, `D3DPOOL_DEFAULT`, 4-bit-per-texel compressed: about 256 MB of source art at BC1/BC3 |
| geometry | 48 | vertex and index buffers, static and per-frame; the game's own meshes are small |
| audio | 36 | music and effects plus the decoder's buffers, 48 kHz stereo float |
| game heap | 68 | the decompiled game's own allocations — the pool that must not fragment |
| shaders | 4 | compiled Xenos blobs and state blocks, from `programs.xsh` |
| spare | 4 | the resolve target and the swap chain's back buffer |

Pools are allocated at boot and never grow. The console's allocator fragments under a long session and the game's heap is
the one that must hold: a pool that grows at level 40 is a pool that fails at level 80.

## The framebuffer: 10 MB of EDRAM, and the frame does not fit

At 1280×720 the frame's targets are:

| Target | bytes |
|---|---|
| colour, 32-bit, 2× multisampled | 7,372,800 |
| depth, D24S8, 2× multisampled | 7,372,800 |
| **total** | **14,745,600 (14.06 MiB)** |

That is more than the 10 MB the daughter die holds, so the scene is drawn in **predicated tiles**: two passes over half
the frame's height each (1280×360, 7,372,800 bytes per pass), with the driver clipping geometry to the tile it is drawing.
`XenosDevice::begin_scene_tiles()` / `end_scene_tiles()` bracket the scene; the resolve then reads the multisampled target
into a plain texture the scaler shows. The tiling is why the port keeps `kPredicatedTiling` in the tuning header rather
than in a shader: it is a property of the machine, and the driver wants the scissor as a `D3DRECT`.

If a frame ever exceeds the EDRAM — a large custom shadow map, say — the answer is another tile, not a smaller resolution.

## The CPU: six hardware threads, five used

Xenon is three cores with two threads each. Core 0 thread 0 belongs to the kernel and the guide, so the port plans around
it:

```cpp
inline constexpr ThreadPlan kThreads{2u, 4u, 5u, 3u, 1u};
//                                game helper render audio stream
```

- **game (2)** and **helper (4)** — the host's frame thread and the game module's job thread, on different cores so a
  job cannot block the frame.
- **render (5)** — command recording and the submit, apart from the game so a long record never eats the step.
- **audio (3)** — the XAudio2 render driver. Its own core: at 10.7 ms a block the mixer must never wait behind a frame.
- **streaming (1)** — pak reads and texture uploads.

Every thread is pinned with `XSetThreadProcessor`; a thread the kernel moves away from its core is a jitter source with no
upside on a fixed machine.

## Streaming

The disc peaks around 12 MB/s on its outer edge; an installed hard disk does 60 MB/s. Pak reads are 64 KB requests with
four queued behind them, and 2 MB per frame is the texture upload ceiling — enough to fill a level's new art in a few
frames without stalling the frame that wants it.

```
kReadChunkBytes             64 KiB
kReadQueueDepth             5
kTextureUploadBytesPerFrame 2 MiB
```

## Shaders: one generation, cooked ahead of time

Xenos runs **Shader Model 3.0** vertex and pixel programs. The game's GX programs are translated to HLSL and compiled for
the console ahead of time (`tools/dev/compile_programs.py --target xenos`, on a build box with the SDK's compiler), one
blob per program and variant, into `programs.xsh` beside the game's data. Nothing is compiled at run time: on a 733 MHz
core with no JIT budget, a shader compiled during a level load is a stall the player feels.

Two consequences worth stating:

- The shader cache is a packaging artefact. A build without `programs.xsh` presents nothing; the log says so.
- Variants are the port's own business. The game asks for a program by GX state; the cache's keys are that state, and a
  key with no blob is a visible fallback (flat colour) rather than a crash.

## Textures

BC1/BC2/BC3 for everything that compresses, uncompressed BGRA8 for the targets and the UI (the UI is drawn at 1:1 and
cannot take block artefacts). Uploads go through `XGSwizzleRect`: the Xenos tiles textures in 32×32 blocks and the driver
owns that layout, so a texture upload is a swizzle, not a `memcpy`. The cooking step (`tools/xbox360/cook.py` in the port
tree) writes rows tightly packed and big-endian; the swizzle takes them from there.

## Audio

48 kHz stereo float, straight into XAudio2 — no 32 kHz Wii sample rate anywhere in the path, because the console has no
fixed-function audio block and the port's mixer resamples once. Four 512-frame blocks of ring is 42.7 ms of slack: a frame
that runs 30 ms long costs the mixer nothing it did not already have.

## What is not measured

No console, no SDK and no hardware were available while this tree was written, so **these numbers are the console's
documented budgets and the port's decisions, not measurements**. The first hardware session should read the boot line in
`Hdd:\Nebula\nebula.log` (free memory, panel, mode) and watch the FPS row in the settings menu against a known-heavy
level; the frame telemetry (`NEBULA_RELEASE=OFF`) reports the step, submit and present times so the split above can be
checked rather than trusted.
