# Publication and initial CI evidence — 2026-10-13

This snapshot supersedes historical statements that GitHub publication was blocked. It does not approve Linux graphics, Darling, shader translation or Riot execution.

## Publication

- Public repository: https://github.com/Stoltembergg/CompatLoL
- Initial published commit: `595777d4aeaf73afb4e26df99ed115766af2f0c0`.
- Remote recursive tree verified: 44 files, not truncated; no `.work`, private logs, publication keys or proprietary binaries.
- Temporary write deploy key was revoked through Composio. The repository deploy-key list was subsequently empty, and the local private/public key files were removed.

## Observed Linux host checks

[Host workflow](https://github.com/Stoltembergg/CompatLoL/actions/runs/38473072737), at the initial commit:

- [Ubuntu debug](https://github.com/Stoltembergg/CompatLoL/actions/runs/38473072737/job/115556841847): completed successfully; downloaded job log shows 8/8 CTest checks passed.
- [Ubuntu sanitizer](https://github.com/Stoltembergg/CompatLoL/actions/runs/38473072737/job/115556842150): completed successfully; downloaded job log shows 8/8 CTest checks passed. Python and the unbuilt LLVM probe are not sanitizer-instrumented.
- Observed Ubuntu 24.04.5 runner image `20261004.327.1`, GNU C++ 13.3.0 and OpenSSL 3.0.13. These are host-contract tests, not Indium compilation or Linux ABI compatibility evidence. The macOS jobs were still running at this observation.

## LLVM audit dispatched, results pending

[Manual standalone audit](https://github.com/Stoltembergg/CompatLoL/actions/runs/38473132073) was dispatched through Composio at the initial commit. Both `audit (14)` and `audit (18)` jobs were observed in progress on Ubuntu 24.04 runners. No final phase report has yet been collected; no configure/build/probe/translation success is inferred from dispatch or running jobs.

Functional LLVM baseline remains unestablished. The approved metallib fixture list is empty; even a successful build/probe must remain build-only until lawful fixture translation and SPIR-V validation pass. CI exit 2 is intentional for blocked/build-only results, not an approved baseline. No GPU, Darling installation or Riot session was requested or run.
