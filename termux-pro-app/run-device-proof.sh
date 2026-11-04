#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
apk=${1:-proof/build/outputs/apk/debug/proof-debug.apk}
app_id=com.anthracitelabs.termuxpro
mode=${2:-e01}
case "$mode" in
  e01) gate=E0/E1; log_name=proof.log; intent=run_proof; limit=25 ;;
  e2) gate=E2; log_name=e2-proof.log; intent=run_e2; limit=60 ;;
  *) echo 'Expected proof mode e01 or e2' >&2; exit 2 ;;
esac
adb get-state >/dev/null
adb install -r "$apk"
adb shell am force-stop "$app_id"
adb shell run-as "$app_id" rm -f "files/$log_name"
adb shell am start -W -n "$app_id/.ProofActivity" --ez "$intent" true
mkdir -p build/evidence
for ((attempt=0; attempt<limit; attempt++)); do
    if adb exec-out run-as "$app_id" cat "files/$log_name" > build/evidence/device.log 2>/dev/null; then
        if grep -qE "$gate candidate probes=|$gate=FAIL" build/evidence/device.log; then
            cat build/evidence/device.log
            grep -q "$gate candidate probes=PASS" build/evidence/device.log
            exit
        fi
    fi
    if ! adb shell pidof "$app_id" > /dev/null; then
        echo "$gate FAIL: app process exited before completing the proof" >&2
        exit 1
    fi
    sleep 1
done
echo "FAIL: no completed $gate report within $limit seconds" >&2
exit 1
