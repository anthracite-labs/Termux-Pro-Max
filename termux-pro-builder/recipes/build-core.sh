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
        export CFLAGS="$CFLAGS -ffile-prefix-map=$source_dir=openssh-source"
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
    ca-certificates)
        mkdir -p "$stage_dir$prefix/etc/tls"
        install -m 0644 "$source_dir"/cacert-*.pem "$stage_dir$prefix/etc/tls/cert.pem"
        ;;
    curl)
        export CFLAGS="$CFLAGS -ffile-prefix-map=$source_dir=curl-source"
        "$source_dir/configure" --prefix="$prefix" --host=aarch64-linux-android --build=x86_64-pc-linux-gnu \
            --enable-shared --disable-static --with-openssl="$sysroot$prefix" --with-zlib="$sysroot$prefix" \
            --with-ca-bundle="$prefix/etc/tls/cert.pem" --without-ca-path --without-ca-fallback \
            --without-libpsl --without-brotli --without-zstd --without-libidn2 \
            --without-nghttp2 --without-nghttp3 --without-ngtcp2 --without-quiche \
            --without-libssh2 --without-libssh --without-librtmp --without-gssapi \
            --disable-ldap --disable-ldaps --disable-docs
        make -j"${TP_JOBS:-2}"
        make DESTDIR="$stage_dir" install
        ;;
    git)
        export CFLAGS="$CFLAGS -ffile-prefix-map=$source_dir=git-source"
        # API 30 includes Bionic iconv; no opaque libiconv target dependency is needed.
        printf '#include <iconv.h>\nint main(void) { iconv_t c = iconv_open("UTF-8", "UTF-16LE"); return c == (iconv_t)-1 ? 1 : iconv_close(c); }\n' | "$CC" -x c - -o iconv-probe
        cd "$source_dir"
        # API 30 Bionic exposes explicit-endian UTF-16/32; Git must add the BOM itself.
        # android-11.0.0_r48/libc/bionic/iconv.cpp (__parse_encoding).
        export ac_cv_iconv_omits_bom=yes
        export ac_cv_fread_reads_directories=no ac_cv_snprintf_returns_bogus=no
        ./configure --prefix="$prefix" --sysconfdir="$prefix/etc" \
            --host=aarch64-linux-android --build=x86_64-pc-linux-gnu \
            --with-openssl="$sysroot$prefix" --with-curl="$sysroot$prefix" --with-shell=/bin/sh \
            --without-tcltk --without-expat
        # Host generators use /bin/sh; the compiled target shell is managed Bash.
        # CC_LD_DYNPATH suppresses sysroot RUNPATH injection; LDFLAGS retains only PREFIX/lib.
        # NO_RUST selects upstream C compatibility implementations, without a new target runtime.
        make_flags=("prefix=$prefix" "gitexecdir=$prefix/bin" SHELL_PATH=/bin/sh \
            "SHELL_PATH_CQ=\"$prefix/bin/bash\"" "CFLAGS=$CFLAGS" "LDFLAGS=$LDFLAGS" \
            "CURL_CONFIG=$sysroot$prefix/bin/curl-config" CURL_LDFLAGS=-lcurl CC_LD_DYNPATH= \
            NO_GETTEXT=YesPlease NO_PERL=YesPlease NO_PYTHON=YesPlease NO_TCLTK=YesPlease \
            NO_EXPAT=YesPlease NO_RUST=YesPlease NO_INSTALL_HARDLINKS=YesPlease RUNTIME_PREFIX= DEFAULT_PAGER=cat)
        make -j"${TP_JOBS:-2}" "${make_flags[@]}"
        make "${make_flags[@]}" DESTDIR="$stage_dir" install
        ;;
    *) echo "Unknown core recipe: $TP_PACKAGE" >&2; exit 1 ;;
esac
