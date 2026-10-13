# Reproduction and unimplemented stages

Host: `cmake --preset debug && cmake --build --preset debug && ctest --preset debug`. Repeat with sanitizer preset. Eight CTest checks (when Python3 is available) test parser contracts, host-report serialization, CPUID feature consistency, monotonic structured log fields, strict doctor arguments, unconditional execution refusal, read-only inspection, an open native ABI fixture and 24 Python audit-harness regressions. Python tests are not ASan/UBSan-instrumented. Linux-only distribution/overlayfs branches remain unverified locally. They do not check Linux Darling or graphics. No eligible GPU/benchmark check has run.

For deterministic standalone LLVM selection and private structured results, use the [Linux audit harness](linux-audit.md). Its real macOS preflight and run reports are blocked before subprocesses. The manual Linux workflow is not remotely executed.

Historical upstream audit configuration:

```sh
cmake -S .work/upstream/indium -B .work/build/indium -DENABLE_TESTS=ON
cmake -S .work/upstream/darling -B .work/build/darling -DCOMPONENTS=gui -DTARGET_i386=OFF -DENABLE_METAL=ON
```

Observed here: Indium configure exit 1 (missing Vulkan library/includes); Darling configure exit 1 (missing Setcap). Do not substitute fake setcap or macOS libraries to make these checks green. Retry on real Linux x86-64 with dependencies from pinned upstream docs. Verify recursive checkout finished before integrated build. Record LLVM version only after a successful build.

Future mandatory matrix: AMD, NVIDIA, Intel physical devices with kernel/driver/ICD/device IDs, Vulkan features, resolution and workload hash. All presently untested. Lavapipe is functional-only, never native performance evidence. Fixtures compare integer exact, float abs <=1e-5+1e-4*abs(ref), deterministic RGBA8 within 2/channel outside explicit raster borders. Benchmarks: 10s warmup, 60s sample, five repetitions, same host, cold/warm caches separated, p50/p95/p99. No benchmark implementation or performance result exists yet.

Full application scenarios, Metal shaders, presentation, audio/TLS and Riot gates remain pending. See acceptance.json. Hardware omissions must be skipped/blocked explicitly, never inferred from host tests.
