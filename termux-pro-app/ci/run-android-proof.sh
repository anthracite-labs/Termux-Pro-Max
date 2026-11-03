#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
apk=${1:?usage: run-android-proof.sh PROOF_APK}
evidence=build/evidence/android-arm64
mkdir -p "$evidence"
printf 'E0/E1=UNVERIFIED\nE2/E3=NOT RUN\n' > "$evidence/status.txt"
# The emulator action exposes its port, but does not export ANDROID_SERIAL.
export ANDROID_SERIAL="emulator-${EMULATOR_PORT:-5580}"
collect_logs() {
    local result=$?
    trap - EXIT
    adb logcat -d -v threadtime > "$evidence/logcat.log" 2>&1 || true
    adb exec-out run-as com.anthracitelabs.termuxpro cat files/proof.log \
        > "$evidence/app-proof.log" 2> "$evidence/app-proof-error.log" || true
    printf 'exit_code=%s\n' "$result" >> "$evidence/status.txt"
    exit "$result"
}
trap collect_logs EXIT
{
    git rev-parse HEAD
    shasum -a 256 "$apk"
    adb shell getprop ro.product.cpu.abi
    adb shell getprop ro.build.version.sdk
    adb shell getprop ro.build.fingerprint
    adb shell uname -m
    adb shell getconf PAGESIZE
    adb shell getenforce
} > "$evidence/device-environment.log" 2>&1
abi=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
kernel=$(adb shell uname -m | tr -d '\r')
policy=$(adb shell getenforce | tr -d '\r')
test "$abi" = arm64-v8a
test "$kernel" = aarch64
test "$policy" = Enforcing
bash run-device-proof.sh "$apk" 2>&1 | tee "$evidence/proof-run.log"
# A launcher start alone cannot pass: require the full native driver result set.
for variant in protected execve execvp spawnp raw relative; do
    grep -Fx "case=$variant exit=0 expected=0" build/evidence/device.log
done
grep -Fx 'case=unregistered exit=64 expected=64' build/evidence/device.log
grep -Fx 'case=bad-arguments exit=65 expected=65' build/evidence/device.log
printf 'E0/E1=PASS (this ARM64 emulator run only; matrix incomplete)\nE2/E3=NOT RUN\n' > "$evidence/status.txt"
