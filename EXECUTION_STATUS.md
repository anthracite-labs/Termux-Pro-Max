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
| T07 package contract | PARTIAL | Python producer and production Java consumer pass host/static checks; Android loading pending |
| T08 toolchain/backend | PARTIAL | NDK/compiler/key/source pins and doctor implemented; immutable host image and clean CI acceptance pending |
| T09 source build | IMPLEMENTED, local and Ubuntu CI passed | Bash/ncurses/readline built from pinned, signature-verified sources; runtime acceptance pending |
| T10 package generation | PARTIAL | Packages/bootstrap generated; inventory, ELF and dependency checks pass; Android loading pending |
| T11 CI parity | PARTIAL | Source-builder and proof APK Ubuntu CI passed; terminal APK CI configured; release host-image pin still pending |
| T12 terminal screen | IMPLEMENTED, acceptance pending | Pinned Apache terminal renderer, keyboard controls and Unicode/ANSI test APK; real UI/accessibility review pending |
| T13 PTY/session | IMPLEMENTED, Android acceptance pending | Native PTY plus host resize/Ctrl+C/startup-error tests pass; Android job-control/lifecycle matrix pending |
| T14 bootstrap/install | IMPLEMENTED, Android acceptance pending | Java contract consumer, staging, ownership, journal/rollback, launcher repair and host crash/HOME tests pass |
| T15 app integration | TEST HARNESS READY, NOT RUN | APK bundles source-built Bash; physical-device instrumentation pending |
| T16 Git/OpenSSH | IN PROGRESS | Bash/OpenSSH/Git nine-package clean source build and Python/Java static closure pass; actual Android package execution pending |
| T17 GH/real E3 | PENDING | Source-build GH and record actual GH → Git → SSH execution |
| T18 Python/Node | PENDING | Sources/dependencies, resources and subprocess device probes |
| T19 importer hardening | PARTIAL | Shared negative archives, central-directory validation, tamper/crash/HOME tests pass on host; broader adversarial/device review pending |
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
The terminal candidate is now implemented; see continuation below. Release remains blocked by the open
runtime, host-image, signing, license/security and distribution gates.

### Builder automation continuation

Ubuntu source-builder CI now compiles the same Bash closure and uploads candidate
packages/bootstrap plus corresponding verified upstream sources and build inputs.
The source-offer regression checks every recorded member hash and rejects a
tampered cached source. Three builder unit tests pass locally. CI execution is
pending observation; it does not replace Android acceptance.

## Terminal/bootstrap continuation

Source builder, host regression and proof APK jobs passed in Ubuntu run
[41749639363](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41749639363)
for branch commit `1618f9a3558dcdc8c583f65338cc8dfcf1cdcdf2` (PR merge checkout).
Published artifacts include `termux-pro-source-bootstrap`, corresponding source,
source-build logs, and the proof APK. This is actual build/static evidence only.

The new `:app` candidate bundles that bootstrap, validates the shared package
contract in Java, rejects unsafe ZIP/ELF/identity/hash inputs, and stages a complete
prefix with ownership records. Atomic renames plus a durable journal recover the
previous prefix after interruption before commit. HOME is outside the transaction.
Unchanged installs verify payloads and repair managed links after APK relocation;
modified/corrupt payloads require the explicit Repair action. This is not package
isolation within the app UID, an external package downloader, or a release.

The terminal uses only pinned Apache-licensed Termux rendering libraries, with
provenance/notices and a separate native PTY implementation. Public descriptor
ownership replaces upstream hidden-field reflection; process startup failures are
reported/reaped and PID-zero signaling is guarded. The protected launcher uses
AT_EXECFN and registered managed entries, then the Android system linker. It
ignores forged argv0 for identity and strips unsupported loader injection variables.
Bash remains an upstream source-built package with narrow path/configure patches.

Actual local results: 23 app/native host tests PASS, six shared/evidence tests PASS,
three builder tests PASS; source-built package closure also passes the Android
Java consumer's static checks. Terminal assembleDebug/lintDebug PASS (no lint
errors; warnings remain). Physical-device instrumentation is implemented and
compiled separately; **not run**. Android E2, E3, app PTY/bootstrap/UI acceptance,
rotation/background/accessibility, 16 KB and broader compatibility remain open.

## Committed core-source checkpoint

Ubuntu run [41757237782](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41757237782)
passed all four jobs: host-proof, source-builder, android-apk and terminal-apk.
The downloadable terminal/test APK artifact is
[termux-pro-apk](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41757237782/artifacts/13289021173).
This proves builds/static checks for `6a2d15b`, not device execution. The follow-up
closed-session resize guard is `18259ac`; it adds a device-regression assertion.

The next branch adds signature-verified zlib/OpenSSL/OpenSSH source inputs and
candidate client recipes. zlib and OpenSSL package/static checks pass locally.
OpenSSH clients compile/link with narrow Bionic HOME, sentinel, bzero and resolver
adaptations, but their embedded host source filenames still need remapping before
package verification can pass. Five builder unit tests pass. No Android SSH, Git,
GH, E2 or E3 pass is claimed. Git/GH/Python/Node and release gates remain open.

### OpenSSH clean-build result

A complete clean CLI build now passes for zlib 1.3.2, OpenSSL 3.5.9 and the
OpenSSH 10.6p1 client package. Source filenames are mapped during OpenSSH compile;
the host-path verifier remains enforced. All three package static checks and the
OpenSSH dependency check pass; the production Java consumer also accepts the
six-package local Bash-plus-SSH closure. Android SSH/runtime acceptance is NOT RUN.
Git/GH/real E3 and Python/Node remain outstanding.


## Git source-build checkpoint (4 November 2026)

Clean source build of ncurses/readline/Bash/zlib/OpenSSL/OpenSSH/CA/curl/Git:
**PASS_STATIC**, including Git 2.56.0, curl 8.23.0 and dated 2026-10-20 CA data.
Actual Git/curl source signatures and compressed hashes verified. Git signatures
cover the separately hash-verified uncompressed tar. The CA carrier has a pinned
checksum and MPL license, without an upstream detached signature.

curl's real Android output and SONAME are `libcurl.so`; the required package
output and Git HTTP helper DT_NEEDED agree. No `.so.4` alias was fabricated.
Git uses upstream C compatibility implementations and Bionic iconv; only unsupported
pthread cancellation-state calls are guarded on Android. Fixed managed Bash,
managed helper path, private RUNPATH, Android linker, dependency closure, templates,
CA bytes and compiled CA path pass static checks. Host source paths remain rejected.

Commands run from the core-source worktree (with existing caches preserved):

```sh
TP_NDK_HOME=/workspace/android-tools/sdk/ndk/28.2.13676358 TP_SOURCE_CACHE=/workspace/source-inputs TP_OUTPUT_DIR=/workspace/checkpoint-builds/pr3-combined-20261104 ./termux-pro-builder/build.sh bootstrap bash openssh git
TP_OUTPUT_DIR=/workspace/checkpoint-builds/pr3-combined-20261104 ./termux-pro-builder/build.sh test git
TP_OUTPUT_DIR=/workspace/checkpoint-builds/pr3-combined-20261104 ./termux-pro-builder/build.sh test openssh
TP_OUTPUT_DIR=/workspace/checkpoint-builds/pr3-combined-20261104 ./termux-pro-builder/build.sh test bash
/workspace/android-tools/jdk-21.0.9+10/bin/javac -Xlint:all -d /workspace/scratch/checkpoint-pr3-java termux-pro-app/app/src/main/java/com/anthracitelabs/termuxpro/bootstrap/*.java termux-pro-app/tests/BootstrapHost.java
/workspace/android-tools/jdk-21.0.9+10/bin/java -cp /workspace/scratch/checkpoint-pr3-java com.anthracitelabs.termuxpro.bootstrap.BootstrapHost closure /workspace/checkpoint-builds/pr3-combined-20261104/packages shared/target.json
python3 -m unittest discover -s termux-pro-builder/tests -v
python3 -m unittest discover -s shared/tests -v
```

All listed checks PASS; builder nine tests and shared/evidence six tests.
Production Python validation accepts all nine packages; the Java Android consumer
also accepts the complete nine-package closure. Independent bootstrap/source ZIP
index/member SHA-256 audits pass. Exact local commands/output are in
`/workspace/scratch/checkpoint-pr3-*`; compiled candidates and corresponding source
remain in `/workspace/checkpoint-builds/pr3-combined-20261104`. These local artifacts
record the working baseline plus dirty build-input identity; CI must independently
build the final pushed revision. CI now builds this combined profile and passes
its same-run bootstrap to terminal APK assembly.

Earlier diagnostic failures (curl required filename, Git configure cross-run,
unsupported Bionic cancellation calls, Rust default, host-sysroot RUNPATH) were
resolved without weakening package validation; failed artifacts/logs are preserved.
Build warnings include upstream cross-compile assumptions and API-macro redefinition.
No actual Android Git/SSH/HTTPS, E2, E3 or terminal runtime pass is claimed.
No GH, Python or Node implementation was started. Release gates remain open.

## Review checkpoint: PR #2 path aliases and PTY assertion (4 November 2026)

Equivalent ancestor aliases of the fixed compiled app prefix now compare by
canonical filesystem identity. The prefix itself must remain a real directory;
registered targets and command names remain constrained. Other private roots,
symlinked registry files/prefixes, forged identity and invalid targets are rejected.
The Android acceptance fixture captures all three TTY checks before redirecting
its result file. Its actual TTY-report prologue passes on a Linux PTY and fails
for pipe descriptors; this is host regression evidence only.

Local commands, from `/workspace/termux-terminal-fix`:

```sh
JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10 python3 -m unittest discover -s termux-pro-app/tests -v
python3 -m unittest discover -s shared/tests -v
TP_NDK_HOME=/workspace/android-tools/sdk/ndk/28.2.13676358 TP_SOURCE_CACHE=/workspace/source-inputs ./termux-pro-builder/build.sh bootstrap
termux-pro-app/app/build-native.sh /workspace/android-tools/sdk/ndk/28.2.13676358 /workspace/scratch/checkpoint-pr2-native
JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10 ANDROID_HOME=/workspace/android-tools/sdk GRADLE_USER_HOME=/workspace/android-tools/gradle-home termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
/workspace/android-tools/sdk/build-tools/36.0.0/apksigner verify termux-pro-app/app/build/outputs/apk/debug/app-debug.apk
```

Results: **27 app/native tests PASS**, **6 shared/evidence tests PASS**; fresh
Bash/ncurses/readline source bootstrap PASS_STATIC; ARM64 native ELF/interpreter/
16 KB alignment checks PASS_STATIC; app and instrumentation APK assembly PASS;
Android lint **0 errors, 3 warnings**; debug APK signature verifies. Local logs
are `/workspace/scratch/checkpoint-pr2-{host,shared,bootstrap,apk}.log` and native
metadata is `/workspace/scratch/checkpoint-pr2-native.json`.

Android E2, actual source-built package execution and terminal instrumentation
remain **NOT RUN**. E0/E1 remain scoped to the supplied OPPO fixture and original
evidence revision. No release, universal compatibility or PR merge is authorized.


## Integrated clean Git checkpoint

PR #2 path/PTY commit `9320ef1f0d6460b2ffecd0a710711d87269eebb0` was normally
pushed before integration. Its exact-head Ubuntu run
[41766303775](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41766303775)
passed host-proof, source-builder, proof APK and terminal APK jobs.
The core branch integrates that history by a normal local merge, preserving both
workstreams and their status records; neither pull request is merged.

Integrated local checks: 27 app/native, six shared/evidence, nine builder tests
PASS; Java closure=9 PASS_STATIC; ARM64 native build and ELF/interpreter/16 KB
metadata checks PASS_STATIC. Debug app/test APK assembly and APK signature PASS;
lint has **zero errors, four warnings** (two fixed `/data/` identity constants,
pinned Gradle version, pre-Android-12 backup declaration). Inspection of the actual
APK verifies that it bundles all nine packages from the correct combined bootstrap,
with matching outer and package SHA-256 values.

Exact integrated commands (repository `/workspace/Termux-Pro-Max`):

```sh
JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10 python3 -m unittest discover -s termux-pro-app/tests -v
python3 -m unittest discover -s shared/tests -v
python3 -m unittest discover -s termux-pro-builder/tests -v
/workspace/android-tools/jdk-21.0.9+10/bin/javac -Xlint:all -d /workspace/scratch/checkpoint-integrated-java termux-pro-app/app/src/main/java/com/anthracitelabs/termuxpro/bootstrap/*.java termux-pro-app/tests/BootstrapHost.java
/workspace/android-tools/jdk-21.0.9+10/bin/java -cp /workspace/scratch/checkpoint-integrated-java com.anthracitelabs.termuxpro.bootstrap.BootstrapHost closure /workspace/checkpoint-builds/pr3-combined-20261104/packages shared/target.json
termux-pro-app/app/build-native.sh /workspace/android-tools/sdk/ndk/28.2.13676358 /workspace/scratch/checkpoint-integrated-native
JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10 ANDROID_HOME=/workspace/android-tools/sdk GRADLE_USER_HOME=/workspace/android-tools/gradle-home TP_BOOTSTRAP_DIR=/workspace/checkpoint-builds/pr3-combined-20261104 termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
/workspace/android-tools/sdk/build-tools/36.0.0/apksigner verify termux-pro-app/app/build/outputs/apk/debug/app-debug.apk
```

Logs/audits: `/workspace/scratch/checkpoint-integrated-{host,shared,builder,java,native,apk}.log`,
`checkpoint-integrated-native.json`, `checkpoint-integrated-apk-audit.json` and
`checkpoint-pr3-bundle-audit.json` in the same scratch directory. Local APKs retain
their accurate pre-commit `+dirty` identity. The final pushed commit's independent
CI result must be observed and linked in PR #3; a queued/running check is not PASS.
Initial dirty-file backups remain in
`/workspace/checkpoints/termux-20261104T031108Z/{pr2,pr3}`; previous source caches,
build outputs and diagnostic evidence were preserved.

E0/E1 remain PASS only for the original user-supplied OPPO proof fixture/revision.
Actual Android E2, E3, source-built Git/SSH/HTTPS and terminal acceptance remain
NOT RUN. No further implementation phase or release is authorized by this checkpoint.
