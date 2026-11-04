#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ndk_dir=${1:?usage: build-native.sh NDK_DIRECTORY OUTPUT_DIRECTORY}
output_dir=${2:?missing output directory}/arm64-v8a
assets_dir="$(dirname "$2")/proofAssets"
repo_root=$(cd ../.. && pwd)
compiler="$ndk_dir/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
mkdir -p "$output_dir"
for fixture in probe driver; do
    name=launcher
    if [[ "$fixture" == driver ]]; then name=driver; fi
    "$compiler" -std=c11 -Wall -Wextra -Werror -fPIE -pie \
        -Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 \
        "native/$fixture.c" -o "$output_dir/libtp-$name.so"
done
mkdir -p "$assets_dir"
for fixture in target launcher driver; do
    extra=()
    output="$assets_dir/e2-target"
    if [[ "$fixture" != target ]]; then
        extra+=("$repo_root/shared/native/tp_exec.c")
        output="$output_dir/libtp-e2-$fixture.so"
    fi
    "$compiler" -std=c11 -Wall -Wextra -Werror -fPIE -pie \
        -Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 \
        -I"$repo_root/shared/native" "native/e2-$fixture.c" "${extra[@]}" -o "$output"
done
python3 - "$assets_dir" <<'PY'
from pathlib import Path
import hashlib, sys
p = Path(sys.argv[1])
(p / 'e2-target.sha256').write_text(hashlib.sha256((p / 'e2-target').read_bytes()).hexdigest() + '\n')
PY
