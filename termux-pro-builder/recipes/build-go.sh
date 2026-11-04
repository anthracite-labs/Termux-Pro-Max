#!/usr/bin/env bash
set -euo pipefail
cd "${TP_SOURCE:?}"
prefix=${TP_PREFIX:?}
destination=${TP_STAGE:?}$prefix
mkdir -p "$destination/bin"
# NDK external linking produces Android PIE + PT_INTERP/DT_NEEDED, never a static Go target.
# Go's package assets and help/license resources are embedded by upstream go:embed.
flags="-s -w -linkmode=external -extldflags '-Wl,-z,max-page-size=16384 -Wl,-z,relro -Wl,-z,now -Wl,-rpath,$prefix/lib'"
flags+=" -X github.com/cli/cli/v2/internal/build.Version=${TP_VERSION:?}"
flags+=" -X github.com/cli/cli/v2/internal/build.Date=${TP_BUILD_DATE:?}"
"${TP_GO:?}" build -p "${TP_JOBS:-2}" -trimpath -buildvcs=false -buildmode=pie \
    -ldflags="$flags" -o "$destination/bin/gh" ./cmd/gh
