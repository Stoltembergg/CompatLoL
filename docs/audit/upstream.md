# Upstream source audit (partial)

Pinned sources are unmodified clones under `.work/upstream/`. This report distinguishes inspected code from runtime behavior; no upstream runtime/GPU test passed here.

## Darling

Revision `60ba801decee7a00782f74f6be4c8ffb013f79ff` (2026-09-06). `CMakeLists.txt:3` targets Linux; `COMPONENTS=gui`, `TARGET_i386=OFF`, `ENABLE_METAL=ON` are actual options. Metal auto-mode checks Vulkan and llvm-config; a build that silently disables Metal would not satisfy this project's graphics gate. GUI component includes system/dev_gui_common/iokitd/core. macOS configure fails at required Setcap, before usable runtime build.

Source ownership is modular: `src/external/dyld`, `src/external/darlingserver`, `src/external/libsystem`, `src/external/objc4`, `src/external/libdispatch`, `src/external/libclosure`, `src/external/foundation`, `src/external/cocotron`, `src/external/metal`. Root GPL-3.0 is not a license for all embedded upstream code. Full file-level/license and API audit remains pending; source availability does not prove framework compatibility.

## Darling Metal

Revision `ae20248dc144beab899e38752f5a530f28a0ea56` (2026-03-07, GPL→MPL relicensing merge). MPL-2.0 notices are present in inspected files. `deps/indium` fixes `8423a7d...` (confirmed local recursive checkout). CMake builds Metal over objc/Foundation/Indium and MetalKit over AppKit/QuartzCore; MetalPerformanceShaders uses `src/dummy.c`.

`src/Metal/MTLDevice.mm::ensureDevices` only exposes the default Indium device. `MTLCreateSystemDefaultDevice` returns retained system device when enabled, nil otherwise. `MTLCopyAllDevicesWithObserver` and removal contain observer TODOs. `src/MetalKit/MTKView.m` uses weak delegate, timer-driven state and delegates device/format/size to CAMetalLayer. Do not equate an exported selector with correct behavior.

## Indium

Revision `8423a7d2f053167030d2bc4a227f96243c740667` (2023-04-11). 0BSD; C++17/CMake 3.20, Vulkan 1.3 and LLVM according to README/build. Standalone configure with tests enabled fails here because Vulkan headers/library are absent. LLVM compatibility has not yet been tested.

`src/indium/render-command-encoder.cpp` uses descriptor pool maxSets=64, aborts on failed pool creation, assumes colorAttachments.front(), forces single samples (MSAA TODO), and throws for stencil attachments. Tracks color textures as read/write with TODO to distinguish access. These are observed coverage/safety risks, not demonstrated LoL requirements. `src/indium/drawable.cpp` only defines destructor; presentation belongs to additional layer integration, not this file alone.

## Iridium

Component in Indium, no fourth independent repository. `src/iridium/iridium.cpp::translate` takes AIR library bytes → SPIRV builder → output buffer and OutputInfo. `src/iridium/dynamic-llvm.cpp` loads HOST_LLVM_LIBNAME with dlopen, or Darling `_elfcalls`, and resolves symbols dynamically. CMake derives that name from `llvm-config --link-shared --libnames`. Toolchain and dynamic-library ABI must be tested together. There is no proven compatibility here with modern game metallibs or arbitrary MSL source.

## Actual presentation path

The pinned Cocotron `QuartzCore/CAMetalLayer.mm:529–546` invokes `drawable->synchronizeRender()` with a GPU-side wait, then `glCopyImageSubData` from the drawable OpenGL texture. Its presentation notification contains a FIXME acknowledging inaccurate actual render/present completion. This is an OpenGL interoperability path, not a proven direct Vulkan swapchain. No CPU readback has been demonstrated in this path. Verify export/import synchronization and actual window output on Linux before deciding whether to replace it.

## Maintenance and alternatives

Commit dates are observations of these pinned revisions, not proof of abandonment/current support. Complete release/PR/CI review is still required. No code imported from metal2vulkan, MoltenVK, Wine/DXVK or Mesa. metal2vulkan alpha has changed API/design; evaluate a fixed revision with open failing AIR fixtures before proposing an adapter. SPIRV-Cross reflects/translates SPIR-V outward, not AIR inward; MoltenVK translates Vulkan→Metal. SPIRV-Tools is the planned validation tool, not pixel equivalence proof.

Sources: https://github.com/darlinghq/darling ; https://github.com/darlinghq/darling-metal ; https://github.com/darlinghq/indium . File findings refer to the revisions above, not moving branches.
