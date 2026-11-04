#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
apk=${1:?usage: run-device-acceptance.sh PROOF_APK}
mode=${2:-e01}
case "$mode" in
    e01) gate=E0/E1; log_name=proof.log ;;
    e2) gate=E2; log_name=e2-proof.log ;;
    *) echo 'Expected proof mode e01 or e2' >&2; exit 2 ;;
esac
evidence=build/evidence/device-arm64
mkdir -p "$evidence"
printf '%s=UNVERIFIED\nE3=NOT RUN\n' "$gate" > "$evidence/status.txt"
# Use ANDROID_SERIAL when supplied; otherwise adb requires exactly one attached device.
collect_logs() {
    local result=$?
    trap - EXIT
    adb logcat -d -v threadtime > "$evidence/logcat.log" 2>&1 || true
    adb exec-out run-as com.anthracitelabs.termuxpro cat "files/$log_name" \
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
bash run-device-proof.sh "$apk" "$mode" 2>&1 | tee "$evidence/proof-run.log"
# A launcher start alone cannot pass: require the full native driver result set.
if [[ "$mode" == e01 ]]; then
    for variant in protected execve execvp spawnp raw relative; do
        grep -Fx "case=$variant exit=0 expected=0" build/evidence/device.log
    done
    grep -Fx 'case=unregistered exit=64 expected=64' build/evidence/device.log
    grep -Fx 'case=bad-arguments exit=65 expected=65' build/evidence/device.log
else
    for outcome in 'echo 0' 'exit-1 1' 'exit-127 127' 'sigterm 143' 'static-reject 126' 'wrong-abi 126' 'pty-control 0'; do
        read -r variant code <<< "$outcome"
        grep -Fx "e2case=$variant exit=$code expected=$code" build/evidence/device.log
    done
fi
printf '%s=PASS (this ARM64 device run only; matrix incomplete)\nE3=NOT RUN\n' "$gate" > "$evidence/status.txt"
