---
name: game-perf-budget
description: Diagnoses and fixes game performance problems with frame-time budgets and a measure-first workflow - finding whether a game is CPU-bound or GPU-bound, profiling in Godot, Unity and Unreal, and fixing the usual culprits (per-frame allocations, too many draw calls, overdraw, shadows, physics, Tick). Use when the user reports low FPS, stutter, hitches, frame drops, long load times, high memory, or asks to optimize a game or hit 60/120 FPS on a target device.
license: MIT
metadata:
  author: gamesmith
  version: "0.1.0"
---

# Game performance budget

Never optimize by guessing. The loop is: **measure → find the bound → fix one thing →
measure again.** Report numbers in milliseconds, not FPS: 60 to 50 FPS is 3.3 ms, 30 to
20 FPS is 16.7 ms.

## Frame budgets

| Target | Budget per frame |
| --- | --- |
| 30 FPS | 33.3 ms |
| 60 FPS | 16.7 ms |
| 90 FPS (VR minimum) | 11.1 ms |
| 120 FPS | 8.3 ms |

Leave about 10-20% headroom; a frame that uses the full budget will miss it on spikes.
Ask the user for the **target device**, not their dev PC.

## Step 1: which side is slow?

Compare CPU frame time (game + render thread) with GPU frame time.

| Engine | How to read it |
| --- | --- |
| Godot 4 | Debugger → Monitors (`Time/Process`, `Time/Physics Process`), Debugger → Visual Profiler for CPU vs GPU per frame |
| Unity | Profiler window (CPU Usage + GPU Usage modules); in builds enable "Development Build" + "Autoconnect Profiler" |
| Unreal | Console `stat unit` (Frame, Game, Draw, GPU), `stat gpu`, Unreal Insights with `-trace=cpu,gpu,frame` |

- **GPU time ≈ frame time** → GPU-bound: resolution, overdraw, shaders, shadows, post-processing.
- **Game/main-thread time ≈ frame time** → CPU-bound in game code: scripts, physics, AI, allocations.
- **Render/draw thread ≈ frame time** → CPU-bound on submission: too many draw calls / objects.
- **Average fine but visible hitches** → spikes: garbage collection, shader compilation,
  loading on the main thread. Look at the worst frames, not the average.

Quick GPU test: halve the render resolution. If frame time drops a lot, you are GPU-bound.

## Step 2: usual culprits and fixes

### CPU: game code
- Per-frame work that could be event-driven (polling in `_process` / `Update` / `Tick`).
- **Unity**: allocations in `Update` cause GC spikes. Look for `GC.Alloc` in the Profiler:
  LINQ, string concatenation, `GetComponent` every frame, `new List<>` per frame,
  closures/lambdas. Cache components in `Awake`. Enable incremental GC.
- **Unreal**: actors tick by default. Set `PrimaryActorTick.bCanEverTick = false` unless
  needed, lower `TickInterval`, use timers. Blueprint loops over large arrays are slow:
  move them to C++.
- **Godot**: disable `_process` with `set_process(false)` on idle nodes. Use typed
  GDScript (faster). Move hot loops to C# or GDExtension if profiling proves it.
- Physics: reduce physics tick rate if acceptable, use simple colliders (box/capsule
  instead of mesh), put objects to sleep, use collision layers so fewer pairs are tested.

### CPU: draw submission
- Too many draw calls. Combine meshes, use texture atlases, GPU instancing / MultiMesh
  (Godot), SRP Batcher and GPU Resident Drawer (Unity 6), Nanite or instanced static meshes
  (Unreal).
- Too many visible objects: occlusion culling, LODs, distance culling (visibility ranges
  in Godot, Cull Distance Volumes in Unreal).

### GPU
- Overdraw: stacked transparent particles and UI. Fewer, smaller particles; opaque where possible.
- Shadows: fewer shadow-casting lights, shorter shadow distance, lower cascade count.
- Post-processing: SSAO, SSR, volumetrics, bloom at full resolution. Turn off one by one to measure.
- Resolution: use upscaling (FSR / DLSS / TSR / Godot's FSR 2) instead of native resolution.
- Unreal: check `stat gpu` for Lumen and Virtual Shadow Maps cost; they are expensive on low-end GPUs.

### Spikes / hitches
- Shader compilation stutter: warm up / precompile shaders (Unity: ShaderVariantCollection
  warm-up; Unreal: PSO precaching; Godot 4.4+ ubershaders reduce it).
- Loading on the main thread: use async loading (`ResourceLoader.load_threaded_request` in
  Godot, Addressables async in Unity, `StreamableManager` / async load in Unreal).
- Instantiating many objects at once: pool them.

## Step 3: report

After each fix, report: what changed, frame time before → after (ms), on which device, and
the next biggest cost. Stop when the target budget with headroom is met.

## Instrument your own code

- Godot: `Performance.add_custom_monitor("game/enemies", func(): return enemies.size())`
- Unity: `using (new ProfilerMarker("AI.Update").Auto()) { ... }` (Unity.Profiling)
- Unreal: `TRACE_CPUPROFILER_EVENT_SCOPE(AI_Update);` shows up in Unreal Insights
