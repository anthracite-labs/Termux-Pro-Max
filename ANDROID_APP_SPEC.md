# Termux Pro Android App — Implementation Specification

**Status:** implementation requirements; the scoped E0/E1 observation is recorded in [VERIFICATION.md](VERIFICATION.md).
**Source:** user-supplied *Termux Pro Architecture Report* as the baseline; research-backed corrections in [ARCHITECTURE.md](ARCHITECTURE.md).  
**Shared interface:** [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md). Sources cited as `[S#]` are indexed in [README.md](README.md#evidence-register).

## 1. Objective and user-visible success

| Plain language | Engineering requirement |
|---|---|
| Open a real terminal on Android. | Draw ANSI/VT output, accept keyboard input and run an interactive Bash session attached to a real PTY. |
| Run software we built ourselves. | Bootstrap only builder-produced, verified ARM64/Bionic packages compatible with the fixed application prefix. |
| Programs can start other programs. | Validate `bash -> gh -> git -> ssh` via managed command entries, including Go direct-exec behavior. |
| No unnecessary runtime services. | Do not maintain a daemon resolver, modified Bash, generic package manager or custom linker unless evidence makes one necessary. |
| User files remain private. | Preserve `HOME` and app sandbox, and never claim package-level isolation within one UID. |

**MVP scope:** brand-new app; arm64-v8a; proposed Android 11+ minimum; one terminal session initially; Bash; minimal bootstrap; launch proof; controlled import of approved bundled package artifacts. Tabbed sessions, background jobs UI, full package repository, root, Docker and alternate ABIs are deferred.

## 2. Android components and authority boundaries

| Component | Role | Decision |
|---|---|---|
| Activity / terminal view | Terminal glyphs, scrollback, IME, focus, resize, copy/paste, session controls | Required. Prefer reviewed open-source terminal rendering rather than inventing emulator behavior. [S3] |
| TerminalSession / PTY bridge | Open PTY pair, create process/session, connect stdin/stdout/stderr, signal/winsize/termination | Required. Native JNI PTY library is a *candidate*; verify if existing Android APIs/Termux code cover functions. |
| Native command launcher | Minimal entry-point routing to actual dynamically linked target through Android linker | Candidate, not frozen until E1–E3 tests. |
| Bash executable | Interactive shell, syntax/expansion/jobs/command search | Normal source-built package under writable prefix, not a protected fork. |
| Bootstrap installer | Safe extraction and ownership tracking of bundled packages | Required. Not an `apt` clone. |
| Package integrity checks | Verify artifacts and state at install/update and when diagnosing corruption | Required, not per-process sandboxing. |

Android Java/Kotlin app code remains installed through the APK; “only protected launcher” means only one *runnable standalone native command executable*, not that the APK contains no other code or JNI libraries.

## 3. Candidate installation and runtime tree

```text
Android APK / app bundle
  Java/Kotlin application + UI code
  lib/arm64-v8a/libtp-launcher.so   special executable ELF, extracted if proven
  lib/arm64-v8a/libtp-pty.so        real JNI library where required
  assets/bootstrap.*               our own source-built initial package set

Android private data (Context.getFilesDir())
  home/                             HOME, projects, user config/ssh
  usr/                              fixed app-prefix from APP_ID
    bin/                            generated managed commands
    libexec/tp-real/                exported real native executables
    lib/                            shared objects
    share/ etc/ var/lib/termux-pro/ tmp/
```

Do **not** hardcode Android's `/data/app/...` native install directory or infer it from the package name. Discover the native installation directory from Android at runtime; native libraries can remain embedded in the APK depending on packaging settings, and direct-executable packaging requires extraction configuration/testing. [S10]

`$PREFIX` may be compiled into packages, so choose a unique stable `APP_ID` before producing real packages and verify on-device paths. Different Android users/profiles and OEM layouts must not be guessed; if the fixed-prefix model conflicts with an intended supported environment, that is a blocker requiring a new ADR. [S8][S18]

## 4. Startup contract

1. Launch Activity; check app-private filesystem and bootstrap index.
2. For a first run, verify the bundled bootstrap manifest + file hashes and extract with symlink/path traversal protection to private staging.
3. Commit the bootstrap and build the runtime managed command entries. Discover current `nativeLibraryDir` rather than storing an install path forever.
4. Open a PTY; configure rows/columns and UTF-8; start Bash through the **validated** execution mechanism.
5. Set `HOME`, `PREFIX`, `PATH`, `TMPDIR`, locale and minimal environment. No inherited arbitrary `LD_PRELOAD` or hostile `LD_LIBRARY_PATH` from a user-provided file for privileged setup operations.
6. Attach PTY master to the terminal UI; relay screen bytes, keyboard input, terminal resize, process exit and signals correctly.
7. Subsequent launches must preserve user data and only repair/replace managed, verified runtime files after an explicit detected incompatibility or approved update.

**Failure:** If bootstrap verification fails, display an actionable error and refuse command execution; never silently fetch an untrusted replacement or delete `$HOME`.

## 5. Command execution protocol (candidate)

```text
User input -> normal Bash PATH lookup -> usr/bin/<name>
                                      -> (managed symlink to protected launcher)
                                      -> launcher identifies registered command
                                      -> usr/libexec/tp-real/<name>
                                      -> /system/bin/linker64 + absolute ELF path + argv
                                      -> command / child command
```

**E1 design proof required:** Android kernel `execve()` of a writable symlink pointing into extracted protected native storage, together with identification of the invocation path, has passed the user-supplied OPPO API 36/4 KB fixture only; production routing and broader compatibility are not yet proven. Use `AT_EXECFN` only after observing its behavior on supported Android versions. Never rely on spoofable `argv[0]` alone to authorize a launch. [S1][S2]

**E2 execution proof required:** The launcher must preserve: separate arguments including spaces/empty strings, environment variables (except intentionally stripped unsafe variables), stdin/stdout/stderr, terminal file descriptors, exit status and signal semantics. It must avoid infinite loops when entry points and real files are confused. `linker64` is only for supported dynamic ELF programs, not scripts or arbitrary static binaries. [S2][S16]

**E3 chain proof required:** GH built from source launches Git using normal PATH; Git launches SSH; Python and Node child-process APIs also work. Programs calling absolute writable executable paths directly bypass PATH and must be patched or rejected in the builder. [S15]

**If E1 fails:** Do not keep a broken shortcut design in production. Reevaluate a proven Termux execution interception technique (documenting raw syscalls it cannot capture), explicit command wrappers or APK-bundled executable inventory. Reopen ADR-004; accept the fallback only after an equivalent child-process test. There is no promise of universal binary compatibility.

## 6. Session state and terminal behavior

| Event | Required behavior / verification |
|---|---|
| Start | Create PTY, launch configured shell, show prompt. |
| Output | Correct ANSI colors/attributes, line wrapping, Unicode, wide characters and scrollback. |
| Input | Support physical and soft keyboards, Enter, Ctrl keys, paste and terminal escape sequences. |
| Resize | Update PTY window size and deliver normal SIGWINCH behavior to foreground session. |
| Ctrl+C | Send appropriate interrupt via terminal discipline / foreground process group, not kill app Activity. |
| Ctrl+Z / jobs | Shell job control works with the PTY session and process groups. |
| Pipe and redirection | Bash `a | b`, `> file`, background `&`, `wait` and exit statuses work normally. |
| Exit | Session ends, UI reports exit or returns to new-session action without orphaning processes. |
| Rotate / background | Preserve or explicitly terminate session according to lifecycle policy; never silently discard user files. |
| Crash | On restart, detect interrupted transactions; do not assume background children survived. |
| Keyboard | No command rewriting or shell injection caused by UI escaping mistakes. |

No platform-wide promise of indefinite background execution. Android background limits, notification/foreground service policies and OEM behavior require their own test matrix.

## 7. Package installation and distribution

- **Initial Play-intent build:** bundle a preverified bootstrap with the APK; do not implement direct in-app download of native executable packages from external hosts without a documented distribution-policy review. Google Play's executable-code restrictions are explicit, and manual/user initiated import is not assumed exempt. [S13][S14]
- Builder/installer contract is defined only in [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md), including ownership, validation, staging, rollback and collisions. Do not invent an app-specific manifest format.
- App updates MUST retain user `$HOME`; changing `APP_ID` creates a different Android app and may invalidate compiled `$PREFIX` paths.
- External repository / side-loading channels MAY be designed separately after defining which app variant and policies apply; this is not authorized MVP behavior.

## 8. Security and privacy requirements

- Native programs within the app generally share the app UID and access to writable prefix/home. No per-package sandbox is claimed.
- Do not accept unreviewed executable archives without explicit trust and distribution decisions.
- Verify archive paths and symlinks before extraction; reject files that would escape app-private storage. See [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md).
- Use private app storage, minimum Android permissions and avoid broad shared-storage access by default.
- Credential files under `$HOME/.ssh` must be stored with restrictive Unix modes where supported; never log keys, tokens or environment secrets.
- Protect the app's launcher code through Android app installation, not by misleadingly calling mutable package data “protected”.
- App and builder document source provenance, licenses and update handling. A signature is not permission to perform unsafe operations.

## 9. Exception paths / user messages

| Case | Expected result |
|---|---|
| No bootstrap | First-run setup or explicit repair; no blank crash. |
| Wrong architecture | Reject package with a readable ABI diagnostic. |
| Corrupt `bash` executable | Prevent session start; allow verified restore without deleting `$HOME`. |
| Missing command | Standard Bash `command not found`; no guess-based execution. |
| Broken symlink | Managed-entry repair against verified installed metadata; never select arbitrary target. |
| Unsupported static or wrong-format ELF | Reject before linker launch; clear actionable error. |
| Missing `DT_NEEDED` shared object | Fail cleanly with dependency diagnostic and package identifier. |
| Interpreter script without supported interpreter | Reject or invoke verified interpreter explicitly; never treat it as ELF. |
| Child invokes absolute writable path | Documented incompatibility; patch in builder, not heuristic runtime magic. |
| PTY cannot open | Show terminal startup error; close handles; do not leak subprocesses. |
| Interrupted install | Recover committed package state; leave user data intact. |

## 10. Architecture and usability acceptance criteria

- [ ] Android app installs on the selected supported Android/ABI matrix with its native components extracted as required.
- [ ] Terminal creates real PTY, opens Bash, echoes interactive text, supports Ctrl+C, SIGWINCH and job control.
- [ ] `bash -> gh -> git -> ssh` works without a custom Bash resolver.
- [ ] Absolute-path and raw syscall negative tests produce documented behavior rather than crash or unsupported guarantees.
- [ ] Packages are loaded through the *verified* Android-compatible dynamic route, with no unsafe arbitrary executable fallback.
- [ ] Bootstrap signature/hash and archive-integrity tests pass, and rollback never damages `$HOME`.
- [ ] App survives session close, rotation and bootstrap interruption; installed files remain owned/consistent.
- [ ] Screen-reader/keyboard interaction and UI failure states are tested before production release.
- [ ] Distribution/policy approval exists for the exact Play release feature set; no blanket assumption that native package downloads are allowed.

**Implementation update:** the candidate terminal, native PTY, shared-contract bootstrap consumer and physical-device acceptance harness are implemented. Build/host results are in [EXECUTION_STATUS.md](EXECUTION_STATUS.md). Android runtime acceptance remains pending; the architecture gates are not bypassed.
