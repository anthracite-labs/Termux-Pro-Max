#!/usr/bin/env bash
set -euo pipefail
source_dir=${TP_SOURCE:?}
stage_dir=${TP_STAGE:?}
sysroot=${TP_SYSROOT:?}
prefix=${TP_PREFIX:?}
export CC=${TP_CC:?}
export AR="$TP_TOOL_BIN/llvm-ar" RANLIB="$TP_TOOL_BIN/llvm-ranlib" STRIP="$TP_TOOL_BIN/llvm-strip"
export CFLAGS='-Os -fPIC -fstack-protector-strong -D_FORTIFY_SOURCE=2'
export CPPFLAGS="-I$sysroot$prefix/include -I$sysroot$prefix/include/ncursesw"
export LDFLAGS="-L$sysroot$prefix/lib -Wl,-rpath,$prefix/lib -Wl,-z,max-page-size=16384 -Wl,-z,relro -Wl,-z,now"
export PKG_CONFIG_LIBDIR="$sysroot$prefix/lib/pkgconfig" PKG_CONFIG_SYSROOT_DIR="$sysroot" PKG_CONFIG_PATH=''
mkdir build
cd build
configure=("$source_dir/configure" --prefix="$prefix" --host=aarch64-linux-android --build=x86_64-pc-linux-gnu)
case "$TP_PACKAGE" in
    ncurses)
        "${configure[@]}" --with-shared --without-normal --without-debug --enable-widec --without-ada \
            --without-cxx --without-cxx-binding --without-manpages --without-progs --without-tests \
            --enable-pc-files --with-pkg-config-libdir="$prefix/lib/pkgconfig" \
            --with-default-terminfo-dir="$prefix/share/terminfo" --with-terminfo-dirs="$prefix/share/terminfo"
        ;;
    readline)
        "${configure[@]}" --with-curses --disable-static --enable-shared
        ;;
    bash)
        export bash_cv_dev_fd=whacky bash_cv_getcwd_malloc=yes bash_cv_job_control_missing=present
        export bash_cv_func_sigsetjmp=present bash_cv_unusable_rtsigs=no
        "${configure[@]}" --without-bash-malloc --with-installed-readline --with-curses \
            --disable-nls --enable-multibyte --enable-job-control --enable-readline
        ;;
    *) echo "Unknown GNU recipe: $TP_PACKAGE" >&2; exit 1 ;;
esac
make_flags=()
if [[ "$TP_PACKAGE" == readline ]]; then make_flags+=(SHLIB_LIBS=-lncursesw); fi
make -j"${TP_JOBS:-2}" "${make_flags[@]}"
if [[ "$TP_PACKAGE" == bash ]]; then
    # Upstream install also builds optional example loadable plugins and ignores their errors.
    # Stage the actual shell and its manual explicitly; no example binaries are part of this recipe.
    mkdir -p "$stage_dir$prefix/bin" "$stage_dir$prefix/share/man/man1"
    install -m 0755 bash "$stage_dir$prefix/bin/bash"
    install -m 0644 "$source_dir/doc/bash.1" "$stage_dir$prefix/share/man/man1/bash.1"
    mkdir -p "$stage_dir$prefix/etc"
    cat > "$stage_dir$prefix/etc/profile" <<PROFILE
export PREFIX='$prefix'
export PATH='${prefix}/bin:/system/bin'
export TMPDIR='${prefix}/tmp'
export TERM=xterm-256color
PS1='\\u@termux-pro:\\w\\$ '
PROFILE
    printf '%s\n' '[[ -r "$PREFIX/etc/profile" ]] && source "$PREFIX/etc/profile"' > "$stage_dir$prefix/etc/bash.bashrc"
else
    make DESTDIR="$stage_dir" "${make_flags[@]}" install
fi
