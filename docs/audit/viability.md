# Viability gate — 2026-10-13

This is a partial audit, not an end-to-end demonstration. Host is Darwin x86_64. No Linux kernel, Vulkan GPU test environment, Darling runtime install or Riot authorization is available.

| Axis | Decision | Evidence / next gate |
|---|---|---|
| Darwin runtime | conditional | Darling pinned clone; Linux-only target cannot be validated on this host |
| Metal/Vulkan | conditional | Indium/Iridium source present; standalone configure result below; missing verified LLVM/Vulkan environment |
| Riot x86-64 binaries | conditional | No lawful installation supplied or reviewed; slices unknown |
| mVG/online trust | no-go for current execution | No written Riot authorization or documented realizable trust contract |

No complex runtime, shader translator or platform framework changes are authorized by this partial audit. Continue host tests and documentation only; require complete API audit and Linux test evidence before T04–T06 integration. An unavailable requirement must remain a refusal, not a stub returning success.

The standalone audit harness is now prepared for LLVM 14/18 with Clang 18. The [symbol/provenance audit](llvm-iridium.md) records typed-pointer/metadata risks and unapproved precompiled shader origins; no functional LLVM baseline has been selected. Eight local CTest checks pass, including 24 Python harness regressions. The baseline selector independently requires every successful phase and validated fixture evidence; a passed label alone cannot select a baseline. Fresh preflight/run attempts under `.work/results/llvm-preflight-macos-002/` and `.work/results/llvm-matrix-macos-002/` report `LINUX_X86_64_REQUIRED` and exit 2 before any upstream command. The C++ probe and Linux workflow remain unexecuted.

Historical configuration attempts are recorded privately at `.work/results/indium-configure.log` and `.work/results/darling-configure.log`. No upstream build or GPU correctness is claimed. See acceptance.json for actual states, and upstream.md for confirmed source findings.

Risks: modern LLVM compatibility of the 2023 Iridium code, limited render features, OpenGL/Vulkan presentation interoperability and inaccurate presentation completion, incomplete AppKit/CoreAudio integration, mVG platform confidence, continued availability of x86-64 game components, and mixed upstream licensing.

GitHub: publication-blocked (no gh/authenticated owner). Automated host tests are independent of Linux/Mach-O execution; successful parsing is not evidence that a binary can run.
