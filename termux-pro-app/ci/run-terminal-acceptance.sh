#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
apk=${1:?usage: run-terminal-acceptance.sh TERMINAL_APK TEST_APK}
test_apk=${2:?missing instrumentation APK}
evidence=build/evidence/terminal-device
mkdir -p "$evidence"
printf '%s\n' 'terminal_runtime=UNVERIFIED' 'E2=SEPARATE PROOF REQUIRED' 'E3=NOT RUN' > "$evidence/status.txt"
collect() {
    local result=$?
    trap - EXIT
    timeout 20 adb logcat -d -v threadtime > "$evidence/logcat.log" 2>&1 || true
    timeout 20 adb exec-out run-as com.anthracitelabs.termuxpro cat files/acceptance/terminal-result.json \
        > "$evidence/terminal-result.json" 2> "$evidence/result-error.log" || true
    printf 'exit_code=%s\n' "$result" >> "$evidence/status.txt"
    exit "$result"
}
trap collect EXIT
{
    sha256sum "$apk" "$test_apk"
    timeout 20 adb shell getprop ro.product.cpu.abi
    timeout 20 adb shell getprop ro.build.version.sdk
    timeout 20 adb shell getconf PAGESIZE
    timeout 20 adb shell getenforce
    python3 - "$apk" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as apk:
    print(apk.read('assets/build.json').decode())
PY
} > "$evidence/device-environment.log" 2>&1
abi=$(timeout 20 adb shell getprop ro.product.cpu.abi | tr -d '\r')
policy=$(timeout 20 adb shell getenforce | tr -d '\r')
[[ "$abi" == arm64-v8a ]]
[[ "$policy" == Enforcing ]]
timeout 60 adb install -r "$apk"
timeout 60 adb install -r "$test_apk"
# Delete a previous result before starting; stale PASS cannot validate this run.
timeout 20 adb shell run-as com.anthracitelabs.termuxpro rm -f files/acceptance/terminal-result.json
timeout 180 adb shell am instrument -w -r \
    -e class com.anthracitelabs.termuxpro.TerminalAcceptance \
    com.anthracitelabs.termuxpro.test/androidx.test.runner.AndroidJUnitRunner \
    2>&1 | tee "$evidence/instrumentation.log"
grep -Eq '^OK \([0-9]+ test[s]?\)' "$evidence/instrumentation.log"
timeout 20 adb exec-out run-as com.anthracitelabs.termuxpro cat files/acceptance/terminal-result.json > "$evidence/terminal-result.json"
python3 - "$evidence/terminal-result.json" <<'PY'
import json, sys
record = json.load(open(sys.argv[1]))
assert record['status'] == 'PASS_THIS_DEVICE'
assert record['fixture'] == 'bundled-bash-pty-v1'
assert record['close_reap'] == 'PASS'
assert record['E3'] == 'NOT RUN'
PY
printf '%s\n' 'terminal_runtime=PASS (this installed APK/device fixture only)' \
    'E2=SEPARATE PROOF REQUIRED' 'E3=NOT RUN' > "$evidence/status.txt"
