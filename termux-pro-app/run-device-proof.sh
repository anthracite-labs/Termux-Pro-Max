#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
apk=${1:-proof/build/outputs/apk/debug/proof-debug.apk}
app_id=com.anthracitelabs.termuxpro
adb get-state >/dev/null
adb install -r "$apk"
adb shell am force-stop "$app_id"
adb shell run-as "$app_id" rm -f files/proof.log
adb shell am start -W -n "$app_id/.ProofActivity" --ez run_proof true
mkdir -p build/evidence
for ((attempt=0; attempt<25; attempt++)); do
    if adb exec-out run-as "$app_id" cat files/proof.log > build/evidence/device.log 2>/dev/null; then
        if grep -qE 'E0/E1 candidate probes=|E0/E1=FAIL' build/evidence/device.log; then
            cat build/evidence/device.log
            grep -q 'E0/E1 candidate probes=PASS' build/evidence/device.log
            exit
        fi
    fi
    sleep 1
done
echo 'FAIL: no completed proof report within 25 seconds' >&2
exit 1
