# LLVM/Iridium: source audit and experiment matrix

## Fixed scope

Indium `8423a7d2f053167030d2bc4a227f96243c740667`; no upstream files modified. Iridium is a component within that repository. [Machine-readable symbol references and fixture hashes](iridium-source-inventory.json) enumerate every name in `IRIDIUM_DYNAMICLLVM_FUNCTION_FOREACH`, its direct source references and the SHA-256 of each candidate fixture. `tools/audit_iridium_sources.py` regenerates a new inventory on request, refusing existing output. References are lexical evidence, not runtime coverage.

## Library and header contract

`CMakeLists.txt` selects headers using `find_package(LLVM REQUIRED CONFIG)` but independently invokes bare `llvm-config --link-shared --libnames` to define `HOST_LLVM_LIBNAME`. `src/iridium/dynamic-llvm.cpp` opens that name with `dlopen(..., RTLD_LAZY)` and resolves functions by name. A header/library mismatch can compile and still fail at runtime. Candidate-specific PATH and LLVM_DIR must agree; the probe additionally identifies the actual library behind **each** resolved symbol with `dladdr` and compares canonical paths to llvm-config's libdir/libnames.

`private-include/iridium/dynamic-llvm.hpp` uses `decltype` against the selected headers, and caches dlsym with `std::call_once`. `init()` alone establishes only that the shared library loaded. Resolve all declared symbols before attempting translation. `finit()` does not clear the once flags, so each experiment uses a separate process and never reinitializes the probe.

## Semantic risks (not demonstrated failures)

- `src/iridium/air.cpp:127` derives a pointer's pointee using `LLVMGetElementType`; function-type extraction also uses `LLVMGetElementType(LLVMTypeOf(_function))` at line 428. Presence of the API does not establish correct behavior with modern opaque-pointer IR. Test actual AIR translation rather than assuming LLVM 18 support.
- AIR metadata parsing uses `LLVMGetMDNodeNumOperands`, `LLVMGetMDNodeOperands`, `LLVMGetMDString`, named-metadata traversal and positional indexing. Metadata shapes are an additional contract, not just LLVM ABI. A TODO at air.cpp:421 acknowledges limited assumptions about inspected compiled shaders.
- `LLVMParseBitcode2` and failures during early AIR parsing have TODO/abort paths at air.cpp:22–37. Never feed malformed/fuzzed inputs to this upstream CLI as an automatic smoke test.
- Integer signedness and pointer storage classes contain TODOs. Valid SPIR-V is insufficient proof of correct shader semantics.
- The translator's wrapper returns an output buffer and `OutputInfo`; `mtl2spv` writes a `function-infos` JSON sidecar. A zero-byte output can coexist with its internal success condition, so the harness independently rejects empty/truncated SPIR-V and empty reflection.

## Fixture provenance

The root license is 0BSD, with Ella Stanforth and Darling copyrights. That is not sufficient evidence that every precompiled metallib came from a particular source/toolchain.

`test/basic-compute/shadersrc/add.metal` has **Apple 2020 MIT-style permission and copyright**, and defines `add_arrays`; its accompanying precompiled `add.metallib` has SHA-256 `5bfe7eb51b58024e72e9583ca3656da612625540213cbdf6da7b4e00a003ab91`. Source permission is observed; binary/source equivalence and compiler provenance remain unconfirmed. `test/triangle/README.md` explicitly identifies an Apple render-primitives sample. No Apple/Riot metallib is approved by the current experiment policy.

`config/audit-fixtures.json` therefore intentionally has an empty allowlist. No translator will be run on these fixtures until the approved scope/provenance admits an input. Future approval entries must include a test-relative metallib path, exact SHA-256, license, origin and evidence reference; merely having a file in a clone does not approve it. A source-only MIT notice does not silently authorize an unverified precompiled artifact.

The tests' `ENABLE_TESTS=ON` builds executables and embedded test resources privately; it does not run them. Upstream CMake adds seven demo subdirectories without registering CTest checks. `basic-compute` requires GLFW/glm/xxd, allocates large shared buffers and starts a polling thread after creating a device. The harness never runs that executable.

## Matrix (current evidence)

| LLVM runtime | Compiler choice | Build / symbols / translation | Functional baseline |
| --- | --- | --- | --- |
| 14 | Clang 18 | Blocked here: Darwin host; Linux experiment not executed | None |
| 18 | Clang 18 | Blocked here: Darwin host; Linux experiment not executed | None |

The [Linux harness protocol](../validation/linux-audit.md) records versions actually installed, not a guessed frozen image. LLVM 14 and 18 are research candidates, not supported configurations. A successful standalone build plus probe with no approved translation input is `build-only`, overall blocked, and does not select a baseline. No Linux GPU, Darling runtime, graphics output, performance or Riot compatibility was tested in this delivery.
