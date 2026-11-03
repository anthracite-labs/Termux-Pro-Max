# Android execution proof (T03)

This is an E0/E1 experiment, not the terminal app. It has no package installer,
bootstrap, downloads, PTY or production command dispatcher. No Android gate is
passed merely by building it. See [execution status](../EXECUTION_STATUS.md).

The development application ID is `com.anthracitelabs.termuxpro`. This is a
working identity, not an assertion of domain ownership or a frozen release ID.
The intended primary-user package prefix for future packages is
`/data/user/0/com.anthracitelabs.termuxpro/files/usr`; the proof discovers the
actual files directory using `Context` and records it rather than assuming it.
No release packages are built against that path yet. The harness exclusively uses
`files/proof/run-<random>/usr/bin`, then deletes that run's known entries and empty
directories. It never creates, deletes or replaces commands in `files/usr/bin`.

## Build and host checks

Requires a Linux x86-64 host, JDK 17+ with compiler, Android SDK platform 36,
build tools 36.0.0 and NDK 28.2.13676358 (r28c). Set `ANDROID_HOME` to the SDK.
Gradle 8.11.1 and Android Gradle Plugin 8.10.1 are fixed for this experiment.

```sh
./gradlew :proof:assembleDebug
python3 -m unittest discover -s tests -v
```

The two native files are **PIE executables**, named `.so` only to occupy APK
native-library slots. `useLegacyPackaging=true` requests native extraction;
Android must still demonstrate that the extracted files are executable.
Both use 16 KB linker alignment and API 30 NDK entry points. The second executable
is only a fixture driver; it is not an additional runtime resolver.

## Android check

Attach an arm64 Android API 30+ device/emulator, authorize adb, then:

```sh
./run-device-proof.sh
```

Select a device using `ANDROID_SERIAL` if necessary. The script installs the
debug APK, starts the Activity under its own app UID, runs the probe and writes
`build/evidence/device.log`. You can also open the app and press **Run execution
proof**, then retrieve `files/proof.log` with `adb exec-out run-as`.
The installed proof app and `files/proof.log` remain on device. Per-run fixtures
are cleaned after completion; unexpected files prevent directory deletion and
produce a cleanup failure instead of being recursively removed.

The protected driver invokes the protected launcher directly, then its writable
`usr/bin/gh` symlink using `execve`, PATH `execvp`, PATH `posix_spawnp`, raw
`SYS_execve`, and relative `execve`. Every variant supplies `forged-git` as
`argv[0]`. The probe checks `AT_EXECFN`, normalizes the parent directories of
both the invoked path and expected paths without
resolving away the command name, and compares the resolved file to the expected
protected executable. It also verifies empty, spaced, Unicode, separator and
quoted arguments. Exit 64 means identity/path mismatch; 65 means argument mismatch;
66 means the observed identity differs from the driver's expected identity;
126 in the driver means an exec failure (errno is logged). A kernel reporting
only the resolved launcher path for a symlink must therefore fail the candidate.
Each case has a one-second deadline and its own process group. A timeout kills
the case group and reaps the direct child, logs `timeout=1`, and exits 124.
SIGTERM/SIGINT also trigger cleanup and a distinct `interrupted=<signal>` report.
The Activity's outer 15-second watchdog sends SIGTERM and allows three seconds
for native cleanup before a final forced termination. A timeout is an experiment
failure, not evidence of an Android execution-policy rejection.

`execfn_hex` and `argv0_hex` encode UTF-8 bytes as hexadecimal. Only controlled
fixture arguments are recorded; the proof does not dump the environment.
The driver also expects rejection of an unregistered alias and modified arguments.
The Linux tests additionally demonstrate that
`argv[0]=gh` cannot make direct protected execution identify itself as `gh`.
These checks are **not** production authorization: environment values and the
writable filesystem are controlled by the test, and no TOCTOU protection or
package-ownership registry is implemented here.

The [execution-proof workflow](../.github/workflows/host-proof.yml) runs on PRs
to `main` and pushes to `main`, using Ubuntu 24.04 for all jobs:

- `host-proof` runs the host regressions, shell syntax and whitespace checks.
  Host/tool/source identities and test logs are uploaded as `host-proof-evidence`.
- `android-apk` installs SDK 36/build tools 36.0.0/NDK 28.2.13676358 and Temurin
  21.0.9+10, then builds and lints the APK using the checked-in wrapper. Download
  `termux-pro-proof-apk` from the workflow run for `proof-debug.apk`, `SHA256SUMS`
  and `source-revision.txt`. Build/lint logs are `termux-pro-proof-build-logs`.
- `android-arm64` downloads that exact APK artifact, verifies its hash/revision,
  attempts to boot an API 30 `google_apis;arm64-v8a` emulator, and runs
  `ci/run-android-proof.sh`, which calls the existing `run-device-proof.sh`.
  It requires an `arm64-v8a` guest with an `aarch64` kernel and all eight native
  case results. An x86 guest with ARM ABI translation does not satisfy this test.
  `termux-pro-proof-device-logs` preserves the app log, console output, device
  identity, logcat, and per-run status, including failures. Emulator setup/boot
  failures also leave the status unverified; see the Actions log for boot output.

The Ubuntu ARM64 guest attempt uses software emulation (`-accel off`) with a
five-minute boot deadline and a twenty-minute job limit. Google's Linux emulator
is an x86-64 host binary; modern ARM64 images may be rejected on that host. Such
an infrastructure failure is not an E0/E1 PASS or a measured launcher failure.
No automatic x86-image substitution or ignored emulator failures are permitted.
Only an actual successful Android proof can provide evidence for this matrix
entry; merely adding or passing the APK build job leaves E0/E1 unverified.

Artifact retention is 14 days. Download the APK and device-log artifacts from the
same run; the APK hash/source revision and Android fingerprint/page size identify
what was tested. Host orchestration tests use fake adb responses in isolated
temporary directories and do not produce Android acceptance evidence.

A probe PASS only describes that device/run. Save the APK hash, native ELF
inspection, git revision, exact command, and log alongside the matrix entry in
[VERIFICATION.md](../VERIFICATION.md). API 30, a current Android version, 4 KB,
16 KB and physical-device coverage are still required. E2, E3 and all downstream
package/runtime tasks remain gated. If E1 fails on Android, update ADR-004 before
implementing an alternate route.
