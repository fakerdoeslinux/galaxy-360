# The renderer: what is in, and what the next milestone is

An honest map of the biggest missing piece, so nobody mistakes the platform layer for a finished port.

## What exists

`platform/xbox360/xenos_device.{h,cpp}` — the device and everything below the renderer:

- the D3D9 device at 1280×720, 2× multisampled colour and depth;
- predicated tiles: `begin_scene_tiles()` / `end_scene_tiles()` around the scene's passes;
- `resolve_and_present(true)` — the multisampled target into a plain texture, then the present that ties the frame to the
  panel;
- `create_texture()` / `upload_texture()` — BC1/BC2/BC3 and BGRA8, with `XGSwizzleRect` into the console's 32×32 tiled
  layout;
- `wait_idle()` — an event query, so the next frame's targets are never rewritten under the GPU.

That is the same role `runtime/src/render/vk/vk_context.cpp` and `renderer_vk_frame.cpp` play on the Vulkan side. The
renderer above it is the missing half.

## What the renderer is

Nebula's renderer takes the game's frame as a **record list** (`NebulaFrameList`) — draws, states, texture binds, the
camera and light report — and turns it into API calls. `runtime/src/render/core/` is API-agnostic: `draw_walker.cpp`
walks the records, `pipelines.cpp` and `program_table.cpp` resolve them to programs and state, `compose.cpp` builds
the pass order, `registries.cpp` owns the objects. `encoder_vk.cpp` and `renderer_vk.cpp` are the Vulkan end.

The console's end is a `renderer_d3d9.cpp` plus `encoder_d3d9.cpp` sitting exactly where the `_vk` files sit:

| Vulkan side | D3D9 on the console |
|---|---|
| `vk_context.cpp` — instance, device, queues | `xenos_device.cpp` — **done** |
| `renderer_vk_frame.cpp` — acquire, submit, present | `xenos_device::resolve_and_present` — **done** |
| `pipelines_vk.cpp` — pipeline objects, descriptors | shader blob + `SetVertexShader`/`SetPixelShader` + render states, keyed by the same program table |
| `encoder_vk.cpp` — command buffer recording | direct device calls on the render thread (`DrawIndexedPrimitive`, state setters) |
| uniform/storage buffers | vertex- and pixel-shader constants (`SetVertexShaderConstantF`, c0–c255) |
| push constants | the same constant registers, written per draw |
| descriptor sets, samplers | `SetTexture` + `SetSamplerState` per stage, texture stage 0–15 |
| dynamic rendering / render passes | the implicit D3D9 pass: EDRAM tiles, then the resolve |
| SPIR-V from glslang at build time | HLSL SM 3.0 compiled to `programs.xsh` at cook time |
| FSR 1 / SGSR2 compute passes | full-screen quads with a pixel shader (D3D9 on Xenon has no compute) |

Two console-specific facts shape all of it:

1. **There are no command buffers.** D3D9 records into the device directly, so the render thread owns the device outright
   and the encoder's "recording" is the drawing. The draw walker's state batching — already sorted by program and texture
   — becomes load-bearing rather than an optimisation: a state change on Xenon is a register write through the ring, and
   a thousand of them per frame is a real cost.
2. **The EDRAM is small and the depth buffer is not yours to invent.** Depth test, write and the resolve are fixed
   behaviours of the machine; a pass that wants depth-as-texture needs an explicit resolve, not a copy.

## The shader path

The game's GX pipeline is a texture-environment unit, not a programmable shader. Nebula already translates it to SPIR-V
for Vulkan; the console needs the same translation to **HLSL for SM 3.0**, compiled offline:

```
GX state (TEV stages, indirection, fog, ...) -> HLSL vs_3_0 / ps_3_0 -> compiled blob -> programs.xsh
```

`xbox360_tuning.h` already names the file and the 128-byte alignment Xenos wants for a shader fetch. Keys are the program
table's; a missing blob draws a flat colour and logs once, rather than crashing a level.

Pixel-shader limits that bite: SM 3.0 gives 512 arithmetic instruction slots per program (with a static loop budget), 16
texture samplers, and no bitwise ops. A TEV configuration that needs more than that has to be split into two draws —
which the pass composer can do, since it already splits by blend state.

## The work, in order

Each step ends with something you can look at, which is the only way to build a renderer without the game in front of you.

1. **Clear and present.** `renderer_d3d9.cpp` that clears to a colour, draws nothing, and calls
   `resolve_and_present(true)`. Acceptance: a stable 60 Hz colour on the TV, and `measured_present_hz` reading 59.9–60.1.
2. **One textured quad.** Vertex buffer, a cooked shader, a swizzled texture. Acceptance: a picture appears right way up
   with correct colours (a red/blue swap here is a BGRA/ARGB format mistake, never a shader bug).
3. **The draw walker's first pass.** The scene's opaque draws with the program table resolving to blobs and states.
   Acceptance: a level's geometry visible, sorted wrong is fine, wrong depth is not.
4. **States and blending.** Alpha test, blend, cull, depth write. Acceptance: the HUD and the transparent effects appear
   over the scene instead of through it.
5. **Tiles and resolve, verified.** Compare a two-tile frame against a one-tile frame with `kPredicatedTiling` off.
   Acceptance: identical pixels; a seam means the scissor is wrong.
6. **The passes.** Post-process, bloom and the port's FSR 1 quad. Acceptance: frame time still inside the 4 ms submit
   budget on a heavy scene.
7. **The overlay.** The settings menu draws through the same encoder; acceptance: it opens, navigates with the pad and
   saves, which also proves the constant path.

## Budgets the renderer has to keep

From `docs/PERFORMANCE.md`: 4 ms of submit for a heavy scene, 2 MB of texture upload per frame, and no allocation during
a frame — the pools are sized at boot and the renderer borrows from them.

## Honest status

Steps 1–7 are **not done**. `xenos_device` is the floor they stand on; nothing in this tree has drawn a pixel on a
console. Anyone reading this repository for a playable build should read the table in the README instead of this file.
