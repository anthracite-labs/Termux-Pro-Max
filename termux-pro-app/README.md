# Termux Pro Android implementation

The [E0/E1 proof](proof/) is an experiment, not the final terminal application.
Its protected-executable and managed-symlink fixture passed on the user-reported
OPPO CPH2819 / Android 16 / API 36 / targetSdk 36 / ARM64 / 4096-byte-page device.
[Artifact, source verification and limits](../docs/evidence/oppo-cph2819-api36/README.md)
are recorded separately from newer source changes. E2/E3 device results are NOT RUN.

`shared/target.json` fixes the internal-build identity and primary-user prefix.
Initial distribution bundles verified payloads inside an internally signed APK;
no external native package downloader is authorized or implemented.

## Build

Linux x86-64, JDK/compiler 17+, Android SDK 36, build tools 36.0.0 and NDK r28c
28.2.13676358 are required. Set ANDROID_HOME and JAVA_HOME appropriately:

```sh
./gradlew :proof:assembleDebug :proof:lintDebug
python3 -m unittest discover -s tests -v
```

The [Ubuntu workflow](../.github/workflows/host-proof.yml) publishes
`termux-pro-proof-apk` and build/lint/host logs. Emulator jobs have been removed.

## Physical-device proof

Install/open the generated APK and press Run execution proof, or attach a
compatible authorized Android device and run:

```sh
ANDROID_SERIAL=<device-serial> bash ci/run-device-acceptance.sh proof/build/outputs/apk/debug/proof-debug.apk
```

The wrapper invokes the existing `run-device-proof.sh`, checks ABI/kernel and
SELinux enforcing mode, requires all eight native results, and saves the device
log, logcat and artifact/source identities under `build/evidence/device-arm64`.
When exactly one device is attached, ANDROID_SERIAL can be omitted. No emulator
is created or started. Host orchestration tests use isolated fake adb fixtures;
they never supply Android acceptance evidence.

The E0/E1 fixture stages temporary files only in `files/proof/run-*/usr/bin`.
It does not overwrite actual package entries. Directory aliases retain command
basenames, forged argv0 is ignored for identity, unsupported aliases/arguments
fail, each native child is bounded and reaped, and unexpected cleanup contents
are preserved with a failure. This is not a production command registry or a
same-UID isolation boundary. See VERIFICATION.md for remaining acceptance tests.

## E2 device probe (candidate, Android NOT RUN)

The proof APK now has a **Run E2 linker / PTY proof** button. It copies a
checksum-verified dynamically linked AArch64 ELF asset into its isolated writable
fixture tree, then invokes that target through a protected fixture launcher and
`/system/bin/linker64`. It does not execute the writable target directly.

```sh
ANDROID_SERIAL=<device-serial> bash ci/run-device-acceptance.sh proof/build/outputs/apk/debug/proof-debug.apk e2
```

The seven native cases check separate empty/spaced/quoted/Unicode arguments,
environment/cwd/PID, stdin and an inherited FD, stderr, exit codes 1/127, SIGTERM,
static/foreign-ABI rejection, PTY foreground control, SIGWINCH resize and Ctrl+C.
The system linker determines program argv0 (target-path visibility is a separate
compatibility concern); no universal process-name or arbitrary-binary guarantee
is made. Each child is bounded and reaped. E3 remains NOT RUN.

The same helper/fixture passes a Linux explicit-linker regression with Linux
machine/interpreter constants substituted at compile time. NDK arm64 ELF/static
and APK checks pass. Neither is an Android E2 acceptance result. Save the new
APK/source hash and actual `e2-proof.log` before attributing a device result.

## Terminal candidate (beyond the execution experiment)

`:app` is the single-session terminal candidate. It bundles the builder's actual
source-built Bash/ncurses/readline bootstrap, validates ZIP/package/ELF metadata,
stages a transaction with crash rollback and keeps HOME outside the prefix. The
managed launcher uses the proposed system-linker route; Android acceptance is
pending. Only pinned Apache terminal rendering modules are reused; provenance,
changes and notices are in vendor/README.md. No Termux app or binary package is
used. No remote native package download is implemented.

Build the source bootstrap first, then the APK and real-device test APK:

```sh
../termux-pro-builder/build.sh bootstrap
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
ci/run-terminal-acceptance.sh app/build/outputs/apk/debug/app-debug.apk \
    app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
```

The last command requires a connected ARM64 Android device with SELinux Enforcing;
use ANDROID_SERIAL if needed. It runs a bounded instrumentation test against the
installed APK and writes actual logs/results under build/evidence/terminal-device.
It does not substitute for the separate E2 proof or real GH/Git/SSH E3. It checks
Bash version, a real TTY, managed child arguments, pipe/background wait, resize,
Ctrl+C, Unicode/ANSI text and close/reap. Rotation, full job control, screen-reader
and keyboard usability still need explicit device coverage. Never count compilation
of the test APK as a passing device run.

GitHub Actions publishes `termux-pro-apk` (app plus instrumentation APK, checksums,
source revision and bootstrap digest), separately from `termux-pro-proof-apk`.
Both variants currently use the same application ID and signing key type; they
replace each other. Android debug downgrades may require `adb install -r -d`.
Do not uninstall to switch if you want to preserve app data/HOME.
