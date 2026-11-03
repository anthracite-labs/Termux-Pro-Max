# Android execution proof (T03)

This is an E0/E1 experiment, not the terminal app. It has no package installer,
bootstrap, downloads, PTY or production command dispatcher. No Android gate is
passed merely by building it. See [execution status](../EXECUTION_STATUS.md).

The development application ID is `com.anthracitelabs.termuxpro`. This is a
working identity, not an assertion of domain ownership or a frozen release ID.
The intended primary-user package prefix is
`/data/user/0/com.anthracitelabs.termuxpro/files/usr`; the proof discovers the
actual files directory using `Context` and records it rather than assuming it.
No release packages are built against that path yet.

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
The installed proof app and its test-generated `usr/bin/gh` are left on device.

The protected driver invokes the protected launcher directly, then its writable
`usr/bin/gh` symlink using `execve`, PATH `execvp`, PATH `posix_spawnp`, raw
`SYS_execve`, and relative `execve`. Every variant supplies `forged-git` as
`argv[0]`. The probe checks `AT_EXECFN`, normalizes its parent directory without
resolving away the command name, and compares the resolved file to the expected
protected executable. It also verifies empty, spaced, Unicode, separator and
quoted arguments. Exit 64 means identity/path mismatch; 65 means argument mismatch;
66 means the observed identity differs from the driver's expected identity;
126 in the driver means an exec failure (errno is logged). A kernel reporting
only the resolved launcher path for a symlink must therefore fail the candidate.

`execfn_hex` and `argv0_hex` encode UTF-8 bytes as hexadecimal. Only controlled
fixture arguments are recorded; the proof does not dump the environment.
The driver also expects rejection of an unregistered alias and modified arguments.
The Linux tests additionally demonstrate that
`argv[0]=gh` cannot make direct protected execution identify itself as `gh`.
These checks are **not** production authorization: environment values and the
writable filesystem are controlled by the test, and no TOCTOU protection or
package-ownership registry is implemented here.

A probe PASS only describes that device/run. Save the APK hash, native ELF
inspection, git revision, exact command, and log alongside the matrix entry in
[VERIFICATION.md](../VERIFICATION.md). API 30, a current Android version, 4 KB,
16 KB and physical-device coverage are still required. E2, E3 and all downstream
package/runtime tasks remain gated. If E1 fails on Android, update ADR-004 before
implementing an alternate route.
