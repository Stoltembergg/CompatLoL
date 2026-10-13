# CompatLoL

Experimental open-source macOS → Linux interoperability research. Not affiliated with Riot Games or Apple. **League does not run through this project yet.** No online compatibility is claimed.

## Implemented

C++17 host tooling: bounded Mach-O/FAT parser, static dylib/rpath/import/UUID/version inventory, SHA-256 hashes, basic host report, and fail-closed launcher. JSON 3.11.3 is vendored under MIT; new code GPL-3.0-only. No upstream or Riot binaries are redistributed.

## Build and checks

Requires CMake >=3.20, C++17 compiler and, on Linux, OpenSSL development headers. The local verification environment uses CMake 3.31.6 and AppleClang 17.

```sh
cmake --preset debug
cmake --build --preset debug
ctest --preset debug
cmake --preset sanitizer
cmake --build --preset sanitizer
ctest --preset sanitizer
```

```sh
.work/build/debug/compatlol doctor --json
.work/build/debug/compatlol inspect --bundle /path/to/OWNED-OPEN-POC.app --out .work/results/inventory.json
```

Inspection does not launch programs and skips symlinks. Do not inspect Riot installations before legal review. Output must be a new file outside the inspected directory; existing outputs are refused to prevent hard-link alias truncation. Maximum inspected binary size is currently 256 MiB. Objective-C metadata and bundle version extraction are **not implemented**. The scanner is for trusted, stable local directories, not adversarial filesystems: symlink races are not hardened. `requirements` remains empty rather than inventing behavioral requirements from imports.

`compatlol run` currently refuses **all** profiles. No flag, configuration or authorization file can unlock it. `doctor --json` reports CPU ISA using CPUID (AVX requires OSXSAVE/XCR0), kernel/architecture and display environment presence without exposing socket paths. Linux builds also report distribution and overlayfs support from `/etc/os-release` and `/proc/filesystems`; those branches remain unverified on this macOS host. Vulkan, audio and actual display connectivity remain `not-probed`.

Refusals produce LogV1 JSON on stderr with a per-invocation run ID, monotonic timestamp, process/thread IDs and stable operation code. Filesystem exceptions are redacted to avoid leaking local paths. See `schemas/log-v1.schema.json`. Diagnostic errors must not be interpreted as successful compatibility checks.

## LLVM/Iridium audit harness

A Python 3 stdlib harness prepares isolated Ubuntu 24.04 x86-64 standalone builds for LLVM 14 and 18 with Clang 18. It records tool versions and source revisions, bounds subprocess output/timeouts, verifies LLVM runtime symbols/library identity and validates approved metallib translations with SPIRV-Tools. It never starts a GPU demo, Darling or Riot.

```sh
python3 tools/audit_linux.py preflight --config config/audit-linux.json \
  --out-dir .work/results/preflight-001
python3 tools/audit_linux.py run --config config/audit-linux.json \
  --out-dir .work/results/audit-001
```

On macOS these commands intentionally return exit 2 and a blocked report, without invoking Linux builds. There are no approved shader fixtures yet; successful Linux builds/probes therefore remain `build-only` until provenance is resolved, with no functional baseline. See [symbol/fixture audit](docs/audit/llvm-iridium.md) and [Linux preparation and reproduction](docs/validation/linux-audit.md). The manual GitHub workflow is prepared, not remotely executed. CTest registers the harness regressions when Python 3 is available; sanitizers cover C++ host tooling, not Python or the unbuilt Linux probe.

## Current phase

See [audit and viability](docs/audit/viability.md), [upstream findings](docs/audit/upstream.md), [acceptance status](docs/validation/acceptance.json) and [legal boundary](docs/legal/authorization.md). Linux runtime/physical GPU validation and Riot authorization are unavailable in this macOS session. Upstream clones live only under ignored `.work/upstream/`.

GitHub publication is blocked: `gh` is unavailable and no authenticated owner has been verified. Local Git repository exists; no remote publication is claimed.
