# Termux Pro execution status

This tracks implementation of the engineering blueprint, not just PR #1's initial
experiment. The owner has requested continued independent builder/app development
while runtime gates are addressed. No release or unrun device test is implied.


## Current authoritative checkpoint — after merging PRs #1–#3

**Baseline:** `main` merge sequence was PR #1 (`f369c9eeae88d2d11e121a15c99cb7f0874a329a`), PR #2 (`74dd4918c116c3807e6e9ff47875a3f0403417fb`), then PR #3 (`a0373380045184a45d3c7ef69f2dacdcb26be17f`). PR #2 was retargeted from `feature/execution-proof` to `main` before merging. PR #3's Git history includes PR #2 and its corrected path/PTY assertions. This is a **development code merge, not a release or architecture approval**.

**Exact-head verification before merge:** PR #1 `b5f5661` — [two GitHub jobs passed](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41747074287); PR #2 `9320ef1` — [four jobs passed](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41766303775); PR #3 `27e445b` — [four jobs passed](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863). The PR #3 run passed 27 app/native, 6 shared/evidence, 9 builder host regressions; clean Bash/OpenSSH/Git nine-package source build, Python and Java static package-contract checks, proof APK, terminal APK/instrumentation APK builds and lint. Downloadable artifacts: [terminal/test APKs](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863/artifacts/13293689622) and [nine-package bootstrap, packages and corresponding source](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863/artifacts/13294233074). GitHub Actions artifact retention is limited; record independent digests/provenance. These PR results are not automatically checks on the new `main` merge head.

**Builder implemented:** source-built ncurses, readline, Bash, zlib, OpenSSL, OpenSSH (client-only), CA certificates, curl and Git; signed source input verification where available, hashed CA bundle, package inventory, ELF/SONAME/RUNPATH/dependency checks, external-hash ZIP bootstrap and corresponding-source bundle. Source built and static-validated is **not** Android runtime verified. GH now has a source-built candidate and a real-program Android test route (T17 checkpoint below). Python and Node.js remain unimplemented.

**Android app implemented:** single-session terminal candidate, native PTY, managed protected launcher, archive/ELF/identity validation and transactional bootstrap with crash recovery; the terminal acceptance test now captures TTY status before redirecting its output. Code compiles, but physical Android terminal, E2, Bash/Git/SSH execution, real E3 and full lifecycle/accessibility/16 KB acceptance remain **NOT RUN**.

**Next order:** Android E2 fixture → actual bundled terminal/PTY/bootstrap and Bash/Git/OpenSSH device acceptance → source-build GH and prove real GH → Git → SSH E3 → Python/Node and subprocess acceptance → hardening, API/OEM/16 KB, distribution/signing/license/security, T21 readiness. Builder and device-proof work may advance in parallel when safe; E3 must not block its own package prerequisites.

**Release:** NOT READY. A green Ubuntu workflow is not the same as a passing Android device, an accepted execution ADR or an approved distribution policy. The target remains ARM64, primary Android user, `com.anthracitelabs.termuxpro`, compiled `files/usr` prefix and APK-bundled packages only.


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
| T08 toolchain/backend | PARTIAL | NDK/compiler/key/source pins and doctor implemented; **source CI passes**; immutable host-image digest and release approval still pending |
| T09 source build | IMPLEMENTED, local and Ubuntu CI passed | Nine-package Bash/OpenSSH/Git closure built from verified source inputs (CA bundle hash-locked); actual Android runtime pending |
| T10 package generation | IMPLEMENTED, static checks passed | Nine-package bootstrap, corresponding sources and Python/Java package consumer conformance pass; Android loading pending |
| T11 CI parity | PARTIAL, candidate CI passed | PR #3 source/host/proof/terminal jobs all passed; release host-image pin, Android acceptance and clean release provenance pending |
| T12 terminal screen | IMPLEMENTED, acceptance pending | Pinned Apache terminal renderer, keyboard controls and Unicode/ANSI test APK; real UI/accessibility review pending |
| T13 PTY/session | IMPLEMENTED, Android acceptance pending | Native PTY plus host resize/Ctrl+C/startup-error tests pass; Android job-control/lifecycle matrix pending |
| T14 bootstrap/install | IMPLEMENTED, Android acceptance pending | Java contract consumer, staging, ownership, journal/rollback, launcher repair and host crash/HOME tests pass |
| T15 app integration | TEST HARNESS READY, NOT RUN | APK bundles source-built Bash; physical-device instrumentation pending |
| T16 Git/OpenSSH | IMPLEMENTED, runtime acceptance pending | Git 2.56.0, OpenSSH clients, curl/CA/crypto and Bash nine-package clean source build and Python/Java static closure PASS; Android Git/SSH/HTTPS and child launch NOT RUN |
| T17 GH/real E3 | SOURCE CANDIDATE + ANDROID TEST READY; acceptance pending | GH 2.103.3 / Go 1.27.3 ten-package source build and static consumers PASS; real Android E3 NOT RUN |
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

## Historical source-builder checkpoint — 4 November 2026

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

## Historical terminal/bootstrap continuation

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

## Historical committed core-source checkpoint

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

### Historical OpenSSH clean-build result

A complete clean CLI build now passes for zlib 1.3.2, OpenSSL 3.5.9 and the
OpenSSH 10.6p1 client package. Source filenames are mapped during OpenSSH compile;
the host-path verifier remains enforced. All three package static checks and the
OpenSSH dependency check pass; the production Java consumer also accepts the
six-package local Bash-plus-SSH closure. Android SSH/runtime acceptance is NOT RUN.
Git/GH/real E3 and Python/Node remain outstanding.


## Historical Git source-build checkpoint (4 November 2026)

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

## Historical review checkpoint: PR #2 path aliases and PTY assertion (4 November 2026)

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


## Historical integrated clean Git checkpoint

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


## T17 GH source-builder checkpoint — 4 November 2026

Synchronized with `git fetch origin --prune` and independently confirmed PRs
#1/#2/#3/#5 merged into main. Verified baseline
`fcba37679561cd82105f66dbfea5c7a2214c3b09` was exactly origin/main and passed
`git merge-base --is-ancestor`. PR #5's pre-merge run
[41781293991](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41781293991)
passed; that result is not evidence for this GH change. Read the corrected eight
engineering/status documents before implementation.

The new independent worktree is `/workspace/termux-gh-source-builder`, branch
`feature/gh-source-builder`. Both older worktrees remain at their original commits
(`/workspace/Termux-Pro-Max`: `27e445b`; `/workspace/termux-terminal-fix`: `9320ef1`)
without tracked/untracked changes. Existing caches, packages, logs, original OPPO
attachment and preservation backups were retained. No reset/clean, force push,
destructive rebase, PR merge, Python/Node runtime or unrelated feature was started.

### Implemented candidate and verified inputs

- GH **2.103.3**, official source revision
  `63837fb778d6a39f02be0ce76ff89f2bc8d74bdc`; archive SHA-256
  `1a64dc5be667fa8c6458c0e639292ee1a5e215854705db267882e1bcf865b335`.
  Archive Git tree matches `bda6d94df1932516804907a320cb70e1524339b6`;
  reconstructed signed commit identity and actual GPG signature verify against
  pinned GitHub web-flow key `968479A1AFF927E37D1A566BB5690EEEBB952194`.
- Official Linux amd64 **Go 1.27.3 host** archive SHA-256
  `65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40`;
  Go executable SHA-256
  `5f5eb6d0b2fb6aa0bb5d5f8c5f1c944e0de955c925f0111af92a9d8f79680b5b`.
  Every extracted toolchain file is compared to the verified archive, exact host
  version is checked, and automatic toolchain substitution is disabled.
- All **160 actual Android build modules** have source ZIP h1 and go.mod h1
  recomputed against signed-tree upstream go.sum. Read-only module locks, Go cache
  verification, source ZIP inventory and license notices are enforced. Compilation
  is offline. The corresponding-source bundle includes those exact module inputs,
  GH source/signature/tree evidence, Go host archive with sources/license, build
  inputs and patches. No opaque Android target dependency was downloaded.
- Ordinary upstream GH code uses managed PATH to find Git. A narrow Android-only
  patch returns the fixed managed `bin/gh` entry for self/credential-helper lookup,
  because explicit loading can expose linker64 as os.Executable. Go uses supported
  Android/ARM64 CGO + NDK external PIE linking. ELF interpreter, 16 KB alignment,
  DT_NEEDED (`liblog.so`, `libdl.so`, `libc.so`) and private RUNPATH pass unchanged
  validators. Terminal environment supplies the bundled CA file to Go via
  SSL_CERT_FILE. Actual HTTPS/keyring/authentication/extension behavior is unverified.

### Actual build and regression results

**Fresh ten-package source output/sysroot build PASS_STATIC:** ncurses, readline,
Bash, zlib, OpenSSL, OpenSSH clients, CA certificates, curl, Git and GH. Verified
source archives and the content-addressed Go compiler cache were reused locally;
this is not a measured bit-identical/cold-cache reproducibility claim. Production
Python and Java consumers accept the entire ten-package closure. Independent
bootstrap and corresponding-source ZIP/member hash audits pass (706 source
members, including exactly 160 matching module ZIPs).

**29 app/native + 6 shared/evidence + 14 builder tests PASS.** New coverage rejects
host compiler/cache drift, bad module archives/mod sums, invalid signed source
paths/revisions/trees, bad GH provenance/settings/inventory/licenses/closure and
unverified/stale/mismatched E3 evidence. Local loopback API-data fixture coverage
is host-only.

**Terminal/test/proof APK assembly and lint PASS.** App and instrumentation APK
signatures verify; actual APK inspection binds the correct GH-inclusive bootstrap
and checks native ELF metadata. Lint: app zero errors / **3 warnings** (two fixed
private identity paths and pre-API-31 backup declaration); proof zero errors /
**6 warnings** (native fixture storage, backup declaration, icon and three UI text
warnings). Nothing was suppressed to obtain a pass.

An additional **Linux protocol fixture PASS** used source-built Linux GH 2.103.3,
real host Git/OpenSSH, a loopback-only SSH daemon with new disposable keys, the
same Unix-socket API data fixture, and a nonempty bare repository. GH exited zero
and cloned expected commit `f201d330057a9715c344e3722f2e8b8f143410b1`.
Evidence: `/workspace/scratch/gh-e3-host-w7cjejda/` and
`/workspace/scratch/gh-host-protocol-test.log`. Host Git/SSH and a Linux Go runtime
are distinct from the Android package set; **this is not Android E3 evidence**.

Earlier local failures were preserved and resolved: fetching all optional Go/test
modules exhausted disk, then only their redundant new extraction directories were
compacted while every archive/log was retained; actual build imports select 160
modules. Compiler scratch/cache moved to memory-backed storage. The initial Go
archive check rejected the legitimate top-level directory; a focused negative/
positive archive regression now covers it. A manual diagnostic package initially
omitted the existing normal source-license staging step; the final full CLI build
performs it and passes unchanged strict validation.

During concurrent verification the existing Linux E2 fixture exposed a genuine
lost-SIGWINCH race: READY could be observed before an unconditional pause, losing
the resize wakeup. The minimal fixture fix blocks SIGWINCH and waits atomically
with sigsuspend. A deterministic host test forces delivery before the wait and
failed before/passed after the fix. Raw failing/isolated/forced-race logs and final
passing logs are retained. This repairs test correctness; Android E2 is NOT RUN.

### Exact local commands and evidence

From `/workspace/termux-gh-source-builder`:

```sh
TP_NDK_HOME=/workspace/android-tools/sdk/ndk/28.2.13676358 TP_SOURCE_CACHE=/workspace/source-inputs TP_OUTPUT_DIR=/workspace/checkpoint-builds/gh-final-20261104 TP_GO_HOME=/workspace/gh-host-tools/go1.27.3/go TP_GO_MODULE_CACHE=/workspace/gh-go-cache/modules TP_GO_BUILD_CACHE=/dev/shm/termux-gh-cache GOTMPDIR=/dev/shm/termux-gh-tmp ./termux-pro-builder/build.sh bootstrap bash openssh git gh
TP_OUTPUT_DIR=/workspace/checkpoint-builds/gh-final-20261104 ./termux-pro-builder/build.sh test gh
TP_OUTPUT_DIR=/workspace/checkpoint-builds/gh-final-20261104 ./termux-pro-builder/build.sh test git
TP_OUTPUT_DIR=/workspace/checkpoint-builds/gh-final-20261104 ./termux-pro-builder/build.sh test openssh
JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10 python3 -m unittest discover -s termux-pro-app/tests -v
python3 -m unittest discover -s shared/tests -v
python3 -m unittest discover -s termux-pro-builder/tests -v
/workspace/android-tools/jdk-21.0.9+10/bin/javac -Xlint:all -d /workspace/scratch/gh-java-consumer termux-pro-app/app/src/main/java/com/anthracitelabs/termuxpro/bootstrap/*.java termux-pro-app/tests/BootstrapHost.java
/workspace/android-tools/jdk-21.0.9+10/bin/java -cp /workspace/scratch/gh-java-consumer com.anthracitelabs.termuxpro.bootstrap.BootstrapHost closure /workspace/checkpoint-builds/gh-final-20261104/packages shared/target.json
```

The Gradle commands used environment
`JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10`,
`ANDROID_HOME=/workspace/android-tools/sdk`,
`GRADLE_USER_HOME=/workspace/android-tools/gradle-home`, and
`TP_BOOTSTRAP_DIR=/workspace/checkpoint-builds/gh-final-20261104`:

```sh
termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app :app:stageBootstrap --rerun-tasks
termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug :proof:assembleDebug :proof:lintDebug
/workspace/android-tools/sdk/build-tools/36.0.0/apksigner verify termux-pro-app/app/build/outputs/apk/debug/app-debug.apk
/workspace/android-tools/sdk/build-tools/36.0.0/apksigner verify termux-pro-app/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
```

Raw local results: `/workspace/scratch/gh-final-clean-build.log`,
`gh-final-host-tests-fixed.log`, `gh-shared-tests.log`, `gh-builder-tests.log`,
`gh-e2-lost-wakeup-{red,green}.log`, `gh-static.json`, `gh-java-consumer.log`,
`gh-bundle-audit.json`, `gh-readelf.txt`, `gh-apk-final-build.log`, and
`gh-apk-audit.json` in the same scratch directory. Source-build package/signature/
module logs and complete candidates remain in
`/workspace/checkpoint-builds/gh-final-20261104`.

Local artifacts retain the truthful `fcba376...+dirty` working-tree identity:

| Artifact | SHA-256 |
|---|---|
| GH .tpkg | `99844de55364d2673317588e27ceb5f910f5603c122e460cfb8754a73b6e2852` |
| Android GH ELF | `0881b650cdbabe50a6a7a86bc8b6b6c9c0ce8e74f8d9e659195fba97ddbadba3` |
| bootstrap.zip | `5741a8de298128c63d6b5210d4cc9fccb784a108f6c8f28c3e6121b4b7a5c436` |
| sources.zip | `e8b2986b8965dede54d868ad4a608d936d5090400ef36a15e51a7f84d6f7709a` |
| Terminal APK | `fee1979bce45efb89b0ebf0bad0af4833071cc393966225c48c7658cf81ddf50` |
| Instrumentation APK | `25de2474537ecc9a633f4682abadf8f4059cff3a1454849278fd3b2a2cbefa79` |
| Proof APK | `0d01d59b711a3f7e30f63f97159c7e697fcd08ee6f4e35883b6be70dc358176b` |

### E3 preparation and unresolved gates

[Real-program device route](docs/testing/gh-e3.md): the instrumentation APK contains
`GhChainAcceptance`; `ci/run-gh-acceptance.py` sets up private ADB routes and requires
a successful source-built GH → Git → SSH clone from an ephemeral SSH lab. It
checks run nonce, expected commit, APK/build/installed command/manifest hashes,
Git clone + managed SSH child exit/PID trace, ABI/API/page size and JUnit results.
Failing/absent/stale evidence cannot become PASS. Real credentials are not required;
no device runner/emulator is added to CI.

CI now builds/verifies GH and publishes the same-run ten-package bootstrap, source,
logs and terminal/test APKs. At commit creation the new PR's exact-head CI still
requires observation; its final run/artifact links belong in that PR's results.
Prior PR CI is not automatically a pass for this head.

**E0/E1:** only the original supplied OPPO proof fixture/revision PASS.
**Android E2, full terminal device acceptance and E3:** NOT RUN. GH/SSH/HTTPS,
credential-helper self invocation, authentication, keyring, extensions and wider
OEM/API/16 KB behavior remain unverified. The next independent acceptance work is
physical E2 and terminal validation, then running the documented real E3 lab.
T18 Python/Node was not started. Release/ADR/security/license/host-image/distribution
approval remains blocked. No new PR is merged by this checkpoint.

## SonarQube remediation checkpoint — 4 November 2026

An isolated remediation branch based on PR #6 adds explicit Android cleartext
denial, locked and SHA-256-verified Gradle inputs, Bash acceptance guard fixes,
and a scoped Git object-identity security review with source-substitution tests.
See [the finding-by-finding review and exact validation commands](docs/SONAR_REMEDIATION.md).
Local results: 56 host tests PASS; strict proof/app/instrumentation APK assembly
and lint PASS; existing ten-package Python/Java consumer checks PASS. Clean CI
source builds and fresh Sonar analysis are tracked on the remediation PR; they
are not inferred from these local checks. Android E2, terminal device acceptance
and real E3 remain NOT RUN; original OPPO E0/E1 evidence scope is unchanged.
