# Contributing

New original code uses SPDX GPL-3.0-only. Preserve every upstream license and copyright; do not relicense copied MPL/0BSD/Apple files. Use DCO Signed-off-by commits. Changes to upstream belong in that upstream with a minimal open reproduction and regression test, not a replacement Darwin stack.

Run the CMake/CTest debug and sanitizer presets listed in README. Do not submit SDKs, proprietary applications, metallibs from third parties, packet contents, tokens or memory dumps. Synthetic fixtures only. `.private/` and `.work/` must never be staged.

Do not mark GPU checks passed without physical device/driver evidence. Do not execute untrusted pull requests on privileged GPU runners. Approval to publish research is not approval to access Riot services.
