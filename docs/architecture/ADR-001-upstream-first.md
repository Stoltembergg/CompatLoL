# ADR-001: preserve upstream runtime and stop at unverified gates

Accepted from approved plan. Execution route: original x86-64 Mach-O → Darling loader/dyld → libSystem/objc/Darwin frameworks → Darling Metal ABI → Indium → Iridium AIR/SPIR-V → validated Vulkan pipeline → Linux ICD/GPU. Native CPU instructions only.

Current code is host tooling, not this runtime. Never replace loader/server/frameworks without an open failing case, behavioral contract and regression test. No metal2vulkan fallback is installed. MoltenVK is the inverse direction, not Metal-on-Linux.

Keep integrated dependencies at Darling gitlinks; standalone audit repositories are separate. Cache keys must include shader bytes/entry/constants/interface/translator revision/target capabilities; pipelines additionally device driver and pipelineCacheUUID. Private cache only. No cache exists in this version.

Future synchronization preserves Metal resource semantics, per-resource hazards and completion timeline ownership; no global per-frame waits. Presentation must use the AppKit/QuartzCore window, not a second SDL window, and must avoid CPU readback every frame. These are acceptance requirements, not implemented capabilities.
