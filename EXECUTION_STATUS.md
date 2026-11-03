# Termux Pro execution status

This tracks implementation of the engineering blueprint, not just PR #1's initial
experiment. The owner has requested continued independent builder/app development
while runtime gates are addressed. No release or unrun device test is implied.

## Measured architecture evidence

| Gate | Current result | Scope / evidence |
|---|---|---|
| E0 | PASS, device fixture only | User-supplied OPPO CPH2819 / Android 16 / API 36 / targetSdk 36 / ARM64 / 4096-byte pages |
| E1 | PASS, device fixture only | Same sample; all eight expected exits, protected/PATH/spawn/raw/relative routes and forged argv0 |
| E2 | NOT RUN on device | Implementation in progress; no separate target-loading result supplied |
| E3 | NOT RUN | Requires real source-built GH → Git → SSH integration |
| E4 | NOT RUN on device | Fixed build identity selected; package/runtime acceptance pending |
| E5 | BLOCKED for Play release | Internal bundled APK only; policy/release review remains required |

[Evidence record](docs/evidence/oppo-cph2819-api36/README.md): every archive
manifest checksum and the APK SHA-256 was checked. The v2 APK signature verifies;
its native hashes match an independent NDK fixture build. The source revision is
GitHub merge commit `c54afeecf57b5863088ae9586f01c85a3f9232ee` (parents `df162f0`,
`d70e8d3`); its proof tree matches `d70e8d3`. Do not attribute this result to a newer
HEAD. Raw log provenance is user supplied, without timestamp/signature or
cryptographic log-to-APK binding. Public logs redact installation paths and build
fingerprint; original raw data remains in the supplied attachment/local scratch.
No universal Android, 16 KB, PTY or real-package compatibility is claimed.

## T01–T21 implementation and acceptance

| Task | State | Remaining acceptance |
|---|---|---|
| T01 target/identity | DONE for internal primary-user builds | `shared/target.json`; release channel review is separate |
| T02 authoritative baseline | PARTIAL | Complete toolchain/source pin and policy review while implementation proceeds |
| T03 E0/E1 harness | DONE for the supplied fixture/device | Broader matrix remains T20 work |
| T04 E2 semantics | IN PROGRESS | Compatible ELF and argument/env/FD/cwd/signal/exit evidence on Android |
| T05 child probe | PENDING | Separate fixture proof from actual E3 package-chain acceptance |
| T06 execution ADR | CANDIDATE | E2/E3 evidence; ADR-004 is not final |
| T07 package contract | IN PROGRESS | Shared schema/negative fixtures and both consumers |
| T08 toolchain/backend | IN PROGRESS | Source-only dependency closure, pinned inputs, doctor/clean CI |
| T09 source build | IN PROGRESS | Actually compile Bash/dependencies from verified upstream sources |
| T10 package generation | PENDING | Inventory, ELF/ABI/dependency checks and load acceptance |
| T11 CI parity | PARTIAL | APK/host CI exists; source-builder parity/artifacts follow |
| T12 terminal screen | PENDING | Rendering/input/accessibility runtime checks |
| T13 PTY/session | PENDING | Job control, resize, signals and lifecycle device checks |
| T14 bootstrap/install | PENDING | Verified staged extraction, ownership, rollback and preservation tests |
| T15 app integration | PENDING | Actual bundled Bash/PTTY acceptance |
| T16 Git/OpenSSH | PENDING | Source recipes, dependencies and real device integration |
| T17 GH/real E3 | PENDING | Source-build GH and record actual GH → Git → SSH execution |
| T18 Python/Node | PENDING | Sources/dependencies, resources and subprocess device probes |
| T19 importer hardening | PENDING | Adversarial archives, tampering and interrupted-update tests |
| T20 compatibility/channel | PENDING | API 30/current API, 16 KB and additional OEM coverage; policy review |
| T21 readiness | NOT READY | Required runtime/security/license/distribution gates remain open |

## Automation

Ubuntu host regression and APK build/lint jobs publish downloadable candidate APKs
and logs. The incompatible emulator job has been **removed**. Physical-device
acceptance is available through `termux-pro-app/ci/run-device-acceptance.sh` and
never represented by host/fake-adb tests. No repeated polling workflow is retained.

The original emulator attempts failed before installation because Google's
x86-64-host emulator rejected an ARM64 guest. Those infrastructure failures do
not falsify E1 and are superseded by the separately supplied physical-device
observation, not reclassified as passing Android tests.
