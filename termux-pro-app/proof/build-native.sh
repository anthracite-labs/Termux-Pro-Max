#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ndk_dir=${1:?usage: build-native.sh NDK_DIRECTORY OUTPUT_DIRECTORY}
output_dir=${2:?missing output directory}/arm64-v8a
compiler="$ndk_dir/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang"
mkdir -p "$output_dir"
for fixture in probe driver; do
    name=launcher
    if [[ "$fixture" == driver ]]; then name=driver; fi
    "$compiler" -std=c11 -Wall -Wextra -Werror -fPIE -pie \
        -Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384 \
        "native/$fixture.c" -o "$output_dir/libtp-$name.so"
done
