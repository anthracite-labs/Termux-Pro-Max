# Termux Pro execution status

This tracks implementation of the engineering blueprint, not just PR #1's initial
experiment. The owner has requested continued independent builder/app development
while runtime gates are addressed. No release or unrun device test is implied.

## Measured architecture evidence

| Gate | Current result | Scope / evidence |
|---|---|---|
| E0 | PASS, device fixture only | User-supplied OPPO CPH2819 / Android 16 / API 36 / targetSdk 36 / ARM64 / 4096-byte pages |
| E1 | PASS, device fixture only | Same sample; all eight expected exits, protected/PATH/spawn/raw/relative routes and forged argv0 |
| E2 | NOT RUN on device | Seven-case candidate implemented; no Android target-loading result supplied |
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
| T04 E2 semantics | IMPLEMENTED, Android acceptance pending | Dynamic ELF fixture and Linux linker/PTY regression pass; obtain actual Android E2 log |
| T05 child probe | PENDING | Separate fixture proof from actual E3 package-chain acceptance |
| T06 execution ADR | CANDIDATE | E2/E3 evidence; ADR-004 is not final |
| T07 package contract | PARTIAL | Python producer/verifier and negative fixtures implemented; Android consumer pending |
| T08 toolchain/backend | PARTIAL | NDK/compiler/key/source pins and doctor implemented; immutable host image and clean CI acceptance pending |
| T09 source build | IMPLEMENTED, local build passed | Bash/ncurses/readline built from pinned, signature-verified sources; clean CI pending |
| T10 package generation | PARTIAL | Packages/bootstrap generated; inventory, ELF and dependency checks pass; Android loading pending |
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

## E2 candidate implementation

The proof APK includes a separate dynamic ELF target asset, protected E2 launcher, and seven-case driver. Linux process/PTY regression and NDK ELF/APK build/lint checks pass; **Android E2 remains NOT RUN**. No E3 fixture or host test is promoted to the real source-built GH/Git/SSH gate.

## Source-builder checkpoint — 4 November 2026

The standalone builder now compiles ncurses 6.5, readline 8.2 and Bash 5.2.37
from pinned official GNU source archives. All three detached signatures were
checked against pinned signer fingerprints. Zero-fuzz patches set the internal
Android prefix and correct Bash's wide-curses library selection. The shared
validator rejects wrong identity/ABI/prefix, static or malformed executable ELF,
unsafe archive paths, symlinks, undeclared payload and hash mismatches.

Actual local result: all three packages and bootstrap report `PASS_STATIC`;
Bash's declared dependency closure passes. The app/native host suite passed 14 tests, the shared/evidence suite passed six
tests and the builder suite passed two. The E2 APK builds and Android lint passes.
These results do not establish Android execution of the source-built packages.

The local source build used a working tree; its older output manifests predate
the new dirty-tree/input-digest provenance fix. Those local binaries are not
published as clean-commit artifacts. Rebuild from the pushed revision before
publishing candidate packages. Generated packages, caches and SDKs are ignored.

Next work: source-offer bundle and Ubuntu builder CI/artifact publication; Android
terminal/PTY and transactional bootstrap consumer; then real source-built
Git/OpenSSH/GH and E3, Python/Node, importer hardening and compatibility matrix.
The app terminal has not been implemented. Release remains blocked by the open
runtime, host-image, signing, license/security and distribution gates.

### Builder automation continuation

Ubuntu source-builder CI now compiles the same Bash closure and uploads candidate
packages/bootstrap plus corresponding verified upstream sources and build inputs.
The source-offer regression checks every recorded member hash and rejects a
tampered cached source. Three builder unit tests pass locally. CI execution is
pending observation; it does not replace Android acceptance.
