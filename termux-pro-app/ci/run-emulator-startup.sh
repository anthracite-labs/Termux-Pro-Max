#!/usr/bin/env bash
set -euo pipefail
apk=${1:?usage: run-emulator-startup.sh APP_APK TEST_APK}
test_apk=${2:?missing instrumentation APK}
evidence=termux-pro-app/build/evidence/emulator
mkdir -p "$evidence"
collect() {
    result=$?
    trap - EXIT
    adb logcat -d -v threadtime > "$evidence/logcat.log" 2>&1 || true
    adb shell dumpsys activity activities > "$evidence/activities.log" 2>&1 || true
    adb shell dumpsys window > "$evidence/window.log" 2>&1 || true
    adb shell dumpsys input_method > "$evidence/input-method.log" 2>&1 || true
    adb exec-out screencap -p > "$evidence/screen.png" 2>/dev/null || true
    exit "$result"
}
trap collect EXIT
adb shell getprop ro.build.version.sdk > "$evidence/api.txt"
adb shell getprop ro.product.cpu.abilist > "$evidence/abis.txt"
# x86_64 Google APIs emulator needs ARM64 native translation to install this APK.
if ! grep -q 'arm64-v8a' "$evidence/abis.txt"; then
    echo 'Emulator does not advertise ARM64 translation; cannot test the production APK' >&2
    exit 1
fi
adb install -r "$apk"
adb install -r "$test_apk"
# The GitHub runner exposes a hardware keyboard; still exercise the software IME.
adb shell settings put secure show_ime_with_hard_keyboard 1
adb shell ime list -s > "$evidence/input-methods.txt"
adb shell settings get secure default_input_method > "$evidence/default-ime.txt"
[[ -s "$evidence/input-methods.txt" ]]
adb logcat -c
# Instrumentation cold-starts the Activity itself. A preceding am start would
# initialize/verify the large bundled bootstrap twice, overloading slow emulators.
adb shell am instrument -w -r \
    -e class com.anthracitelabs.termuxpro.TerminalStartupSmoke \
    com.anthracitelabs.termuxpro.test/androidx.test.runner.AndroidJUnitRunner \
    | tee "$evidence/instrumentation.log"
grep -Fx 'OK (2 tests)' "$evidence/instrumentation.log"
