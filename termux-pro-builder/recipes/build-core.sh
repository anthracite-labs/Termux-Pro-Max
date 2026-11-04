#!/usr/bin/env bash
set -euo pipefail
source_dir=${TP_SOURCE:?}
stage_dir=${TP_STAGE:?}
sysroot=${TP_SYSROOT:?}
prefix=${TP_PREFIX:?}
export CC=${TP_CC:?}
export AR="$TP_TOOL_BIN/llvm-ar" RANLIB="$TP_TOOL_BIN/llvm-ranlib" STRIP="$TP_TOOL_BIN/llvm-strip"
export PATH="$TP_TOOL_BIN:$PATH"
export CFLAGS='-Os -fPIC -fstack-protector-strong -D_FORTIFY_SOURCE=2'
export CPPFLAGS="-I$sysroot$prefix/include"
export LDFLAGS="-L$sysroot$prefix/lib -Wl,-rpath,$prefix/lib -Wl,-z,max-page-size=16384 -Wl,-z,relro -Wl,-z,now"
export PKG_CONFIG_LIBDIR="$sysroot$prefix/lib/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$sysroot" PKG_CONFIG_PATH=''
mkdir build
cd build
case "$TP_PACKAGE" in
    zlib)
        export CHOST=aarch64-linux-android
        # The shared-support probe does not define zlib.map symbols; lld is strict.
        export LDFLAGS="$LDFLAGS -Wl,--undefined-version"
        "$source_dir/configure" --prefix="$prefix" --shared
        make -j"${TP_JOBS:-2}"
        make DESTDIR="$stage_dir" install
        ;;
    openssl)
        # OpenSSL has no target dependencies; do not embed host sysroot flags in build-info.
        export CPPFLAGS=''
        export LDFLAGS="-Wl,-rpath,$prefix/lib -Wl,-z,max-page-size=16384 -Wl,-z,relro -Wl,-z,now"
        export ANDROID_NDK_ROOT
        ANDROID_NDK_ROOT=$(cd "$TP_TOOL_BIN/../../../../.." && pwd)
        perl "$source_dir/Configure" android-arm64 -D__ANDROID_API__=30 shared no-tests no-docs \
            --prefix="$prefix" --openssldir="$prefix/etc/tls" --libdir=lib
        make -j"${TP_JOBS:-2}"
        make DESTDIR="$stage_dir" install_sw install_ssldirs
        # Perl maintenance helpers are outside the native-only bootstrap contract.
        rm -rf "$stage_dir$prefix/etc/tls/misc"
        ;;
    openssh)
        # Bionic supplies bzero as a header macro, so a symbol-only Autoconf probe misses it.
        printf '#include <strings.h>\nint main(void) { char b[1]; bzero(b, 1); return b[0]; }\n' | "$CC" -x c - -o bzero-probe
        export ac_cv_func_bzero=yes
        # Clang supports sentinel attributes; do not erase the Bionic header token.
        export CPPFLAGS="$CPPFLAGS -DHAVE_ATTRIBUTE__SENTINEL__=1"
        "$source_dir/configure" --prefix="$prefix" --sysconfdir="$prefix/etc/ssh" \
            --host=aarch64-linux-android --build=x86_64-pc-linux-gnu \
            --with-ssl-dir="$sysroot$prefix" --with-zlib="$sysroot$prefix" \
            --without-pam --without-selinux --without-kerberos5 --without-libedit \
            --without-security-key-builtin --disable-pkcs11 --with-sandbox=no
        # Client-only package. Do not build/install a daemon, privileged helpers or host keys.
        make -j"${TP_JOBS:-2}" ssh ssh-keygen ssh-keyscan
        mkdir -p "$stage_dir$prefix/bin" "$stage_dir$prefix/etc/ssh"
        for command in ssh ssh-keygen ssh-keyscan; do
            install -m 0755 "$command" "$stage_dir$prefix/bin/$command"
        done
        install -m 0644 "$source_dir/ssh_config" "$stage_dir$prefix/etc/ssh/ssh_config"
        ;;
    *) echo "Unknown core recipe: $TP_PACKAGE" >&2; exit 1 ;;
esac
