#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ndk_dir=${1:?usage: build-native.sh NDK_DIRECTORY OUTPUT_DIRECTORY}
output_dir=${2:?missing output directory}/arm64-v8a
repo_root=$(cd ../.. && pwd)
compiler="$ndk_dir/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
mkdir -p "$output_dir"
python3 - "$repo_root/shared/target.json" "$output_dir/target.h" <<'PY'
import json, sys
from pathlib import Path
prefix = json.loads(Path(sys.argv[1]).read_text())['prefix']
Path(sys.argv[2]).write_text('#define TP_PREFIX ' + json.dumps(prefix) + '\n')
PY
common=(-std=c11 -Wall -Wextra -Werror -O2 -fstack-protector-strong -D_FORTIFY_SOURCE=2
    -Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 -Wl,-z,relro,-z,now)
"$compiler" "${common[@]}" -fPIE -pie -include "$output_dir/target.h" \
    -I"$repo_root/shared/native" native/launcher.c "$repo_root/shared/native/tp_exec.c" \
    -o "$output_dir/libtp-launcher.so"
"$compiler" "${common[@]}" -fPIC -shared native/pty.c native/pty-jni.c \
    -o "$output_dir/libtp-pty.so"
rm "$output_dir/target.h"
