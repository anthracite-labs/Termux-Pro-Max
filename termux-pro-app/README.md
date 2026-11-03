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
