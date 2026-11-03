# Execution status — 3 November 2026

Implementation has started on `feature/execution-proof`. The original blueprint
remains the contract; its publication-time statements about absent code are
historical. This record tracks the new implementation without upgrading any
Android architecture gate to PASS.

## Foundation and scope

This PR contains an experimental harness alongside the documentation baseline;
it does not approve the execution architecture or authorize a production release.
For the execution experiment only, use `com.anthracitelabs.termuxpro`, arm64-v8a,
minSdk 30, targetSdk/compileSdk 36 and bundled test fixtures. The development
namespace matches the application ID. Release application identity, compiled
package prefix across Android users/profiles, distribution policy and signing
remain unresolved. The experiment fetches no runtime packages.

| Task/gate | State | Evidence / next action |
|---|---|---|
| T01 target baseline | Partial | Development values above; release identity/prefix not frozen |
| T02 source baseline | Partial | References below; full toolchain/package/policy audit remains open |
| T03 E0/E1 harness | Implemented, Android NOT RUN | `termux-pro-app/`; host regressions are separate evidence |
| T04 E2 linker/process semantics | NOT RUN | Requires Android execution evidence before selecting the route |
| T05 E3 child chain | NOT RUN | Native PATH driver is not source-built GH/Git/SSH |
| T06 execution ADR | BLOCKED | ADR-004 remains proposed until device evidence and review |
| T07–T21 downstream work | Gated | Dependencies in IMPLEMENTATION_PLAN.md remain in force |

## Source baseline checked for this slice

- Android W^X: https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission
  Retrieved 2026-11-03. The text prohibits ordinary `execve` from writable app
  home for apps targeting Android 10. It does not establish our symlink behavior.
  Retrieved page SHA-256: `e110cab47b1aacec0e955814916a2ee85971398e56a5a51887c732c6772b2373`.
- Native extraction: https://developer.android.com/guide/topics/manifest/application-element#extractNativeLibs
  Retrieved 2026-11-03. AGP 4.2+ uses `useLegacyPackaging`; extraction still
  requires actual installation testing. Retrieved page SHA-256:
  `db20e25032a0c99478243cac4cdacb1ee165c9bfc27bf240809efed8ba5c219c`.
- Porting reference (read, no code copied):
  https://github.com/termux-play-store/termux-exec/blob/47633d5df2db3dfea34cef568c6c82a7ba8dcc2e/README.md
  Confirms explicit system-linker routing, static ELF limitations and raw syscall
  interception limits. Does not prove our candidate mechanism.
- Bionic upstream mechanism reference linked by the pinned porting reference:
  https://android.googlesource.com/platform/bionic/+/8f639a40966c630c64166d2657da3ee641303194
  Not a device result or a pin for a toolchain build.

These source checks do not revalidate Play policy or all sources in README.
Page hashes identify retrieved snapshots, not immutable future URLs.

## Original verification at `5820ff4`

Host: Linux x86-64; repository baseline `df162f0`; implementation source is the
original implementation commit `5820ff4`. No builder or package manifest exists yet.
NDK 28.2.13676358, SDK/build tools 36/36.0.0, AGP 8.10.1,
checksum-verified Gradle 8.11.1 and Eclipse Temurin JDK 21.0.9+10 were used.
The JDK archive SHA-256 is
`810d3773df7e0d6c4394e4e244b264c8b30e0b05a0acf542d065fd78a6b65c2f`.

| Check | Result | Command / evidence |
|---|---|---|
| Linux regression tests | PASS, 5 tests | `python3 -m unittest discover -s termux-pro-app/tests -v` |
| Wrapper build + lint | PASS | From `termux-pro-app`: `./gradlew --offline --no-daemon :proof:assembleDebug :proof:lintDebug` with `JAVA_HOME`, `ANDROID_HOME`, `GRADLE_USER_HOME` set to the workspace tool installations |
| Native static inspection | PASS | NDK `llvm-readelf -W -h -l -d`: ELF64 little-endian AArch64, nonzero entry, dynamic segment, `/system/bin/linker64`, PT_LOAD alignment and offset/address congruence at 16 KB |
| APK contents | PASS | Both packaged executable bytes match the NDK outputs; merged manifest requests extraction |
| APK signature | PASS, debug key only | Build-tools `apksigner verify` |
| Shell syntax and patch whitespace | PASS | `bash -n` on scripts; `git diff --check` |
| Android installation / runtime E0/E1 | NOT RUN | `adb devices` lists no devices; no `/dev/kvm` is available |
| Android E2–E5 | NOT RUN | No device or package/runtime implementation for these gates |

Lint has **0 errors and 6 warnings**, retained without suppression: newer Gradle
available, no ChromeOS x86_64 ABI, Android 12 backup-rules recommendation, missing
app icon, and two untranslated fixture labels. This experiment does not contain
user terminal data; backup/privacy configuration must be revisited for the app.

Local outputs (generated, ignored by Git):

- `termux-pro-app/proof/build/outputs/apk/debug/proof-debug.apk`
- `termux-pro-app/build/evidence/build.log`, `static-validation.json`,
  `manifest.txt`, and both `libtp-*.so.readelf.txt` files.
- Lint reports under `termux-pro-app/proof/build/reports/`.

Artifact SHA-256:

| Artifact | SHA-256 |
|---|---|
| Debug proof APK | `5a4531490f5d160c0add3459b3c3cfceb53b6f0dcb9302db343ffb78a0d52160` |
| `libtp-launcher.so` | `a90caca4e18b5e14ea83c5943afaba2696c21ba341dee64ff8bbe95f0529eb3e` |
| `libtp-driver.so` | `f44f096838cf2d7fd2e4866c2138f794f266e19f2583026d88786157daf125b3` |

The host tests exercise six positive launch variants and two negative cases in
the native driver, plus direct argv0 spoofing and explicit identity-loss checks.
They cannot demonstrate Android SELinux, native extraction, Bionic `AT_EXECFN`,
PTY/process semantics or actual GH/Git compatibility. No architecture ADR changes
are warranted from Linux results alone. Next: run
`termux-pro-app/run-device-proof.sh` on the required arm64 Android matrix and
record E0/E1 evidence before proceeding through T04–T06.

## PR #1 review follow-up

The review identified inconsistent directory canonicalization, package-tree
mutation, unbounded child lifetimes, missing CI evidence and an overstated scope
assertion. The scope description above is now neutral; this remains an experiment.

- Both expected and invoked paths canonicalize their parent directories while
  retaining their final basenames. A symlinked-parent regression covers protected,
  PATH, relative and raw-syscall cases without accepting an unregistered alias.
- Runs use fresh `files/proof/run-<random>/usr/bin` fixture trees. Cleanup removes
  only known entries and empty directories, without walking symlinks or modifying
  `files/usr/bin`. The Java preservation check verifies distinct runs, existing
  package data, symlink targets and unexpected-file retention.
- Every native case owns a process group and a one-second monotonic deadline.
  Timeout and SIGTERM/SIGINT cleanup kills the group and reaps the direct child.
  Timeout exits 124 with `timeout=1`; interruption is reported separately. The
  Activity requests graceful native cleanup before its final forced termination.
  Linux tests verify both timeout and termination leave no live direct child.
- `.github/workflows/host-proof.yml` runs on PRs to main and branch pushes with
  read-only repository permissions, immutable action revisions, a five-minute
  job limit and uploaded host/source/tool/test logs. It runs the host regression
  suite plus shell syntax and whitespace checks. Check the PR's current-head
  checks for observed CI status; workflow configuration alone is not a CI PASS.

Local follow-up validation: **9 host tests PASS**; wrapper APK build and lint
PASS (**0 errors, 6 existing warnings**); native AArch64 dynamic ELF/entry-point,
16 KB load alignment, APK byte-preservation, extraction-flag and debug-signature
checks PASS. Shell syntax, YAML parsing and patch whitespace checks PASS.
Host tests now require a JDK/compiler as well as Python and GCC. Logs are under
`termux-pro-app/build/evidence/review-host-tests.log`, `review-build.log` and
`static-validation.json`. Android runtime checks are still **NOT RUN**. No
launcher ADR or E2/E3 architecture gate has been approved.

Follow-up artifacts replace the local outputs above; their SHA-256 values are:

| Artifact | SHA-256 |
|---|---|
| Debug proof APK | `45b4217f3876179a356040af9711c448517eb765f42bc82d65f8acbe93192af3` |
| `libtp-launcher.so` | `c8d7cf7798dce19bfd460c262e0e95097bfed2f3f7a110c980bd42e69a787275` |
| `libtp-driver.so` | `c96974be0e358a1f07f9fa330887dc53c3ba5ad6136fd63d157f0f5833b904e4` |

The first host CI run at `cfd6421` stopped before tests because checkout depth 1
caused Git to report inherited Markdown as newly added lines. A local shallow
clone reproduced this failure. The workflow now fetches depth 2 and checks
`git diff --check HEAD^ HEAD`: PR merge runs check against the base parent and
push runs check against the preceding commit. This retains the whitespace gate
while limiting it to the actual change. Final CI status is recorded on PR #1.

## Android CI build and ARM64 emulator integration

The execution-proof workflow now has Ubuntu 24.04 jobs for host checks, an APK
build/lint, and an ARM64 emulator attempt. It runs on PRs to main and pushes to
main. The build publishes **termux-pro-proof-apk** (debug APK, SHA-256 and source
revision), plus **termux-pro-proof-build-logs**. The emulator job consumes that
same artifact and publishes **termux-pro-proof-device-logs**, including on failure.
All actions are pinned and workflow repository permissions remain read-only.

The emulator configuration is Android API 30 / google_apis / arm64-v8a, software
emulation, with a five-minute boot deadline. The proof wrapper checks the guest's
ABI and kernel architecture, runs the existing E0/E1 proof, requires all eight
native case results and records logs before emulator shutdown. E0/E1 status stays
UNVERIFIED unless these checks actually pass. Host tests of the orchestration use
fake adb data and never count as device evidence.

**Current Android gate state: E0/E1 UNVERIFIED, test execution pending.** Ubuntu's
Google emulator is an x86-64 host binary; rejection of the ARM64 system image or
failure to boot is an infrastructure limitation, not successful Android testing.
Do not substitute x86/ABI translation, ignore the failure, or promote this entry
without successful Android logs. The API/page-size/physical-device matrix and
ADR-004 remain unapproved. E2, E3 and the package builder have not been started.
