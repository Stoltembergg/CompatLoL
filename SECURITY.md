# Security

No anti-cheat bypass, spoofed integrity, forged attestation, identity masking, patching Riot code or private-protocol emulation is accepted. Runtime incapability must remain an explicit error.

No private reporting endpoint is configured before GitHub publication. Do not post sensitive findings or credentials publicly; arrange a private channel with the eventual repository owner first.

The current inventory tool is not a sandbox for hostile filesystems. It bounds binary reads but does not eliminate filesystem TOCTOU races. Riot execution is disabled unconditionally.
