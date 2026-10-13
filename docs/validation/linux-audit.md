# Standalone Linux audit protocol

## Prepare, do not install automatically

Requires a real Ubuntu 24.04 x86-64 host/runner. This macOS session does not provide one; no VM or CPU emulation is created. The harness never calls sudo, installs Darling, applies setcap, creates a DPREFIX, starts a GPU demo or contacts Riot.

On a Linux machine you control, explicitly install the documented dependencies:

```sh
sudo apt-get update
sudo apt-get install build-essential cmake ninja-build clang-18 \
  llvm-14 llvm-14-dev llvm-18 llvm-18-dev libvulkan-dev libglfw3-dev \
  libglm-dev xxd spirv-tools python3 git libssl-dev
sh tools/bootstrap.sh
```

The upstream-audit workflow may do this only on its disposable GitHub runner. No authenticated published GitHub repository has been verified here; that workflow is **prepared, not executed**. No frozen package versions or OS image digest are claimed. Effective versions are recorded by dpkg-query and tool --version commands.

## Commands

Choose a new output directory for every invocation. It must be under `.work/results/`, with no existing output directory or symlink components. Do not use adversarial concurrently modified filesystems.

```sh
python3 tools/audit_linux.py preflight --config config/audit-linux.json \
  --out-dir .work/results/linux-preflight-001
python3 tools/audit_linux.py run --config config/audit-linux.json \
  --out-dir .work/results/linux-matrix-001
python3 tools/audit_linux.py run --llvm-major 14 --config config/audit-linux.json \
  --out-dir .work/results/linux-llvm14-001
```

Exit 0: requested operation passed. Exit 2: environment/dependency blocked, or build-only with no approved translation input. Exit 1: experiment/configuration/contract failed. A preflight pass is only a preflight pass; `operation` distinguishes it from a run and baseline stays null.

Darwin/arm64/other distributions are refused before any subprocess. Missing tools or development packages block the experiment. Dirty/missing/revision-mismatched sources are refused, never reset or patched. Only the standalone Indium checkout is compiled; its locked gitlinks, if present, are checked recursively. `tools/bootstrap.sh` owns source provisioning.

Each LLVM uses `.work/build/audit-linux/<run_id>/llvm-N/`, `/usr/lib/llvm-N/bin` before PATH and `/usr/lib/llvm-N/lib/cmake/llvm` for LLVM_DIR. Clang and clang++ are fixed at `/usr/bin/clang-18` and `/usr/bin/clang++-18`. The experiment strips inherited LD_PRELOAD/LD_LIBRARY_PATH/CMAKE_PREFIX_PATH/LLVM_CONFIG. The actual runtime shared library must canonically match llvm-config's declared library, not merely share a basename.

## Evidence and process lifecycle

Every new output directory contains `report.json`, `config.json` and numbered stdout/stderr logs. Directory permissions are private (0700). Logs are bounded at 16 MiB per stream plus the truncation marker, and pipes continue to drain; timeout kills the command's process group and reaps its direct child. Descendant-held pipes are also bounded by the deadline. Reports record argv, duration, exit code, stage and source revision. Logs and absolute private paths are not uploaded.

Configure budget 300s; each build 3600s; probe/translation/validator 30s. Build parallelism 2. All limits live in `config/audit-linux.json`. One failed LLVM does not abort the other candidate. The smallest major fully passing configure, build, probe and approved translation/spirv-val becomes baseline; `build-only` never does. The selector checks that all required phase records are passed and that nonempty approved-fixture hashes have successful validation records, independently of the candidate's overall passed label. Malformed probe metadata is rejected without corrupting the report schema.

No fixture is currently approved. This is intentional: source auditing found Apple-authored sample shaders and has not established provenance of the accompanying binaries. See `docs/audit/llvm-iridium.md`. The private upstream build may compile its demo targets, but the harness will not execute them or translate the sample metallibs. Missing approved fixtures produces explicit skipped translation stages and `FIXTURE_PROVENANCE_UNCONFIRMED`.

When an input is approved under the project scope, each `config/audit-fixtures.json` entry is:

```text
{relative_path: test-relative metallib path, sha256: exact 64-hex hash,
 license: nonempty reviewed license, origin: nonempty provenance,
 evidence_ref: nonempty review reference}
```

Translation uses a new private output directory, never the source path. The harness checks exit code, file size/magic/alignment, nonempty `function-infos` JSON and `spirv-val --target-env vulkan1.3`. These checks prove artifact validity only, not numerical correctness or rendered pixels. No GPU acceptance is inferred.

## Verification

Run existing CMake/CTest debug and sanitizer presets. The new `audit-harness` test uses isolated synthetic runners for command ordering, LLVM selection, failures and baseline rules, and real short-lived Python subprocesses for log draining/timeouts. It does not compile upstream or simulate a passing Linux result in the acceptance report. The C++ LLVM probe is prepared but cannot be built/verified without Linux/LLVM headers here.

The historical AC01–AC10 remain unchanged in meaning. New harness evidence is separate; no standalone build can approve full Metal/Darling/game criteria.
