# Authorization and Embedded Vanguard

Riot publicly announced Embedded Vanguard inside the macOS game client in patch 25.S1.2 (2025-01-22): https://www.leagueoflegends.com/en-us/news/game-updates/patch-25-s1-2-notes/ . This does not define a public Linux trust contract or grant permission to interoperate.

Current authorization: **none available**. No Riot application has been inspected, started or contacted in this implementation. No user accounts were used. Online tests are blocked, not passed. The launcher refuses every execution profile until reviewed implementation and Linux validation exist.

Before any Riot-specific static analysis or launch: qualified review of regional Riot terms, applicable interoperability law, SDK/Xcode licenses and redistribution obligations. Terms source: https://www.riotgames.com/en/terms-of-service . Preserving bytes does not by itself authorize reverse engineering or third-party interaction.

Future private approval record must identify scope (`static-inspection`, `local-launch`, `connected-session`), approved bundle hash/version, reviewer and document reference. Connected sessions additionally require written Riot authorization naming project, environment, designated accounts and test scope. CLI switches alone are insufficient. This record is a process control, not proof that Riot will trust Linux.

Unknown, not confirmed mVG requirements: platform attestation, identities, code-signing interactions, protected services, IPC and Keychain. Do not apply Windows TPM/Secure Boot rules to macOS by analogy. Never replace a failed trust check with synthetic success or disable mVG. If platform requirements cannot be met honestly, stop and report the incompatibility.

Local/offline launch, full initialization, rendering and approved online match must be recorded separately. Practice and replay are not assumed offline. No proprietary artifacts may enter Git/CI or public repro bundles.
