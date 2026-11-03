# Termux Pro — System Architecture and Decisions

**State:** proposed; validated against upstream information, not against our own device builds.  
**Related:** [README](README.md) · [Builder](BUILDER_SPEC.md) · [App](ANDROID_APP_SPEC.md) · [Package contract](PACKAGE_CONTRACT.md) · [Tests](VERIFICATION.md).

## 1. Responsibility map

| Plain language | Technical responsibility | Owner |
|---|---|---|
| Factory obtains and builds tools | Fetch/verify upstream source, dependency ordering, patches, NDK, binary checks, release artifacts | Builder |
| Package label explains the contents | File inventory, version/dependencies, command exports, integrity information | Shared contract |
| Android terminal displays and controls programs | Terminal emulator, PTY, session lifecycle, user data | App |
| Protected doorway starts commands | Minimal native program-entry routing + system Bionic linker delegation | App (candidate, gated) |
| Shell interprets what a user types | Normal upstream Bash executable | Source-built package |
| Package tools can start other tools | Known command-entry convention and build-time patches | Builder + package contract |

**Dependency flow, one-way:** upstream source + recipes → builder → signed/verified package artifacts → app installer/bootstrap → on-device package tree → launcher → Android linker → program. The app does not depend on the builder at runtime; the builder does not query or modify a running app. Android system tools are dependencies, not components to duplicate.

## 2. System drawing

```text
                  BUILD TIME (Linux / GitHub Actions)
 Verified upstream source ---- reviewed Termux-derived patches
            \                         /
             \                       /
         [ Termux Pro Builder + pinned toolchains ]
                       |
             verified bootstrap/packages
                       |
                artifact boundary
                       v
               RUNTIME (Android)
 +---------------------- APK ----------------------------+
 | Terminal UI + session service                         |
 | JNI PTY bridge (native shared library)                |
 | Protected native launcher candidate (executable ELF)  |
 | Bundled bootstrap archive / manifest                  |
 +-------------------------------------------------------+
                       |
            initialize verified app-private tree
                       v
             files/home  files/usr ($PREFIX)
                           |
           usr/bin/<command>  -> protected launcher
                           |
            usr/libexec/tp-real/<command>
                           |
                  /system/bin/linker64
                           |
                 dynamically linked program
                           |
                   children via PATH
```

The runtime shortcut arrows are a **hypothesis requiring test**. They are not a claim that every arbitrary application executable can be intercepted.

## 3. Runtime storage

```text
APP INSTALLATION (Android chooses directory)
  nativeLibraryDir/
    libtp-launcher.so        special executable ELF in .so-named packaging slot
    libtp-pty.so             actual JNI shared library

APP PRIVATE DATA (Context.getFilesDir())
  home/                     interactive shell home, projects, .ssh
  usr/                     single shared $PREFIX
    bin/                   managed command entry points (symlinks if gate passes)
    libexec/tp-real/       actual executable ELF targets
    lib/                   shared dependencies
    share/                 architecture-independent package data
    etc/                   configuration
    var/lib/termux-pro/    installed package metadata + indexes
    tmp/                   private scratch
```

The path for the app-private prefix is constructed from Android `Context` at runtime. **Before building packages**, choose a unique stable `APP_ID` and validate the absolute prefix that packages embed; Termux documents that many packages have compile-time paths and cannot be mixed across application identities. [S8][S18]

The Android native-library extraction directory is not specified by a fixed string. Android Gradle packaging must be configured and tested to place the executable launcher on an executable filesystem path. A filename ending `.so` does *not* make a normal shared library directly executable. [S10]

## 4. Runtime command chain

### Interactive Bash → GH

1. The app creates a PTY and uses its proven bootstrap/launch path to open the Bash command entry point.
2. The user enters `gh auth login` in normal Bash.
3. Bash's default PATH search finds `$PREFIX/bin/gh`. Bash does **not** need custom command-lookup logic.
4. Conditional on the validated symlink mechanism, `$PREFIX/bin/gh` starts the protected multi-call launcher.
5. The launcher infers the requested command from the verified invocation path (never trusting only mutable `argv[0]`), resolves its *single active* registered program target, checks target safety and format, and executes Android's linker with an absolute ELF target path.
6. GH starts; output, stdin, Ctrl+C, exit status and file descriptors behave like a normal process.

### GH → Git

GH can start Git without consulting Bash. If GH searches PATH for `git`, `$PREFIX/bin/git` reaches the same protected launcher and loads the actual Git executable. If GH issues `execve` against an absolute path in writable storage, that **bypasses** this design. Our source build must patch such call sites or reject the package. Upstream Go code demonstrates raw syscall use; `LD_PRELOAD` alone cannot cover it. [S2][S15]

### Script execution

A script's kernel shebang (e.g. `#!/bin/sh`) does not automatically become a valid Android app-private interpreter path. Package recipes must rewrite supported interpreter paths, and runtime command-entry logic must route scripts to their interpreter explicitly where required. Standard `bash script.sh` is the minimal supported contract. Direct `./script.sh` is **not** accepted as universally working until separately verified. [S2]

## 5. Architecture decision records (ADRs)

### ADR-001 — Source-build packages, not imported third-party binaries

**Status:** accepted as requirement. **Reason:** trust/provenance, fixed ABI and prefix, predictable child-launch behavior. **Alternative rejected:** arbitrary external binary compatibility in first release; it expands the execution and security matrix. **Trade-off:** more compilation maintenance, no guaranteed byte-for-byte reproducibility without explicit reproducibility checks. **Sources:** [S4][S5][S7].

### ADR-002 — Keep Bash as a regular package

**Status:** proposed, strong. **Reason:** Bash supplies shell semantics, not Android execution permission. Modifying Bash to handle every child launch fails when a child launches its own children. **Alternative rejected:** protected `libbash.so` as the only resolver (maintenance fork and misplaced responsibility). **Sources:** [S1][S2][S15].

### ADR-003 — Use one shared `$PREFIX`, not per-package independent runtime roots

**Status:** proposed, strong. **Reason:** upstream packages patch configuration, shebangs, libraries and helpers against a common prefix. **Alternative:** separate `$PREFIX/packages/name` roots require additional linking, loader search and data path rules. **Source:** [S8].

### ADR-004 — One protected multi-call launcher, if proven

**Status:** PROPOSED / BLOCKED on device gate E1. **Reason:** a small executable in protected install storage can delegate target loading to `/system/bin/linker64` and can be reached by standard PATH-based child launches via generated symlinks. **Alternative A:** Termux-style exec-interception (supports many libc entry points; fails for direct raw syscalls, complicates preload inheritance). **Alternative B:** patch every child invocation to explicit `/system/bin/linker64 ...` (smaller runtime, potentially huge recipe burden). **Alternative C:** bundle every executable in APK native-library directory (simplifies direct exec but prevents adding programs later without app updates). **Do not claim selection is proved** until E1/E2 pass. **Sources:** [S1][S2][S10][S16].

### ADR-005 — Separate PTY JNI from launcher executable

**Status:** proposed, strong. **Reason:** the Android UI must own terminal I/O and process/session control; command routing does not. JNI shared library and executable launcher are distinct binary forms and have distinct responsibilities. **Alternative:** reuse existing reviewed Termux terminal-session code if license permits. **Source:** [S3].

### ADR-006 — No runtime `packages.json` address book

**Status:** proposed. **Reason:** package installations already produce authoritative metadata. Installer generates one active command entry per exported command; launcher targets a deterministic `$PREFIX/libexec/tp-real/<entry>` file and does not scan multiple directories on every launch. **Multiple path candidates** are processed **at installation** using explicit priority/provider selection, with ambiguity rejected. **Alternative:** runtime JSON resolution adds parsing, path ambiguity, race conditions and duplicated state. **Source:** architectural simplification, not an Android guarantee.

### ADR-007 — Keep Play distribution separate from package-delivery features

**Status:** REQUIRED REVIEW GATE / not a compliance claim. **Reason:** Play currently restricts apps downloading executable code such as `.so` files from outside Play. We specify a Play-safe-intent MVP that bundles the bootstrap in the APK and does not fetch third-party native executable packages. Off-Play delivery/manual import may be separately designed only after review; user-mediated import is not assumed automatically exempt. **Sources:** [S13][S14].

### ADR-008 — No custom ELF loader or mandatory generic `LD_PRELOAD`

**Status:** proposed. **Reason:** Bionic already loads compatible dynamically linked ELF files when invoked explicitly; our controlled package builder can patch known child launch paths. Revisit interceptors only if measured package compatibility requires them. **Sources:** [S2][S16].

## 6. Important counterexamples / falsification

| Claim | Counterexample | Required response |
|---|---|---|
| “One shortcut catches all processes.” | Package executes `/data/.../usr/libexec/tp-real/git` directly. | Patch at build time or mark package incompatible. |
| “Android linker runs any binary.” | Fully static binary or incompatible ELF interpreter. | Reject package or require a compatible dynamic Android ELF build. |
| “One launcher in protected storage secures packages.” | Malicious process runs under same app UID and overwrites writable package data. | Treat all packages as same trust domain; do integrity checks at install/update, document lack of per-package isolation. |
| “`.so` extension means safe/launchable.” | A JNI shared object lacks standalone entry point; or native libs remain inside APK. | ELF checks + packaging/extraction/device tests. |
| “We can detect command from argv0.” | Caller spoofs argv0. | Verify invocation-path source, resolved command ownership and reject mismatch; test kernel/Bionic behavior. |
| “Build our own Go package and all issues vanish.” | Go runtime may use raw `execve`; upstream Play Termux needed Go-specific fixes. | Test `gh → git`, `go` child execution, process name handling. [S6][S15] |

## 7. Architecture gates that can change the design

- **E1 (mandatory):** actual writable `$PREFIX/bin/gh` symlink to protected `libtp-launcher.so` executes, and launcher identifies `gh` correctly (not solely from `argv[0]`). If false, **reject ADR-004** and choose a measured alternative. No handwaving.
- **E2 (mandatory):** protected launcher successfully `exec`s `/system/bin/linker64 <absolute target>` preserving argument semantics, environment, PTY, signals and exit result; verify 4 KB and 16 KB page devices.
- **E3 (mandatory):** `gh → git → ssh` chained launches work for our source-built package set; absolute path negative test gives a documented failure or patch.
- **E4 (mandatory):** all toolchain and package artifacts use the app-specific prefix and satisfy the [Package Contract](PACKAGE_CONTRACT.md).
- **E5 (release):** policy review supports the actual distribution mechanics before Play submission.

No launcher design is “final” until E1–E3 pass. If E1 fails, the minimum fallback is **not automatically** a second resolver: test the directly invoked system linker plus source-level command wrappers, and compare compatibility cost to an upstream-inspired interception library. Record a new ADR before changing direction.

## 8. Sources and evidence status

- **Verified upstream facts:** Android W^X restriction [S1]; explicit linker launch + its limits [S2]; Termux shared `$PREFIX` assumptions [S8]; Go direct `execve` possibility [S15]; APK native packaging behavior [S10].
- **Project choices / reasoned inferences:** protected multi-call launcher; generated shortcuts; deterministic `tp-real` path; one active provider; build-time patch strategy; package manifest format.
- **Unverified:** exact symlink/auxv invocation behavior under supported Android releases, launcher ELF packaging/execution, device-specific PTY and process behavior, Play approval for any future package delivery.

All `[S#]` definitions and URLs are in [README.md](README.md#evidence-register).
