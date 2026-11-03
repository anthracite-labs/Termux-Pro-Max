# Execution status — 3 November 2026

Implementation has started on `feature/execution-proof`. The original blueprint
remains the contract; its publication-time statements about absent code are
historical. This record tracks the new implementation without upgrading any
Android architecture gate to PASS.

## Foundation and scope

The owner's “Execute” instruction authorizes implementation against the blueprint.
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

## Verification of this implementation slice

Host: Linux x86-64; repository baseline `df162f0`; implementation source is the
commit containing this record. No builder or package manifest exists yet.
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
