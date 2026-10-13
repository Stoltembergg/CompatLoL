# First Linux audit: bootstrap failure — 2026-10-13

Run: https://github.com/Stoltembergg/CompatLoL/actions/runs/38473132073
Commit: 595777d4aeaf73afb4e26df99ed115766af2f0c0

Both LLVM matrix jobs completed with failure. Downloaded job logs identify the same preparation failure: a newly cloned Darling tree was rejected as dirty before its first checkout (`Refusing dirty upstream darling`, exit 2). No candidate audit report was created. This is a bootstrap defect, not LLVM incompatibility. Configure, upstream build, real LLVM probe, translation and SPIR-V validation were not reached.

The bootstrap now checks cleanliness only for an existing checkout, preserving refusal of local modifications; a fresh --no-checkout clone proceeds to its pinned checkout. A network-free regression uses real local Git repositories to verify successful first checkout and preservation/refusal of a dirty existing tree. All 25 Python regressions and 8/8 CTest checks in both local debug and sanitizer presets passed (terminal 843fba85-ae0b-4e6d-9802-93582fd7ab50). Python is not sanitizer-instrumented. The approved fixture list remains empty, and no functional baseline is selected.

The publication document is an earlier in-progress snapshot; this completed failure supersedes its pending-run status. A corrected workflow execution is required before making any upstream build/probe claims.
