# Termux Pro — Verification, Risks and Quality Gates

**Status:** test plan plus recorded device evidence; see the scoped observations below and [execution status](EXECUTION_STATUS.md).
**References:** [Architecture](ARCHITECTURE.md) · [Package contract](PACKAGE_CONTRACT.md) · [App spec](ANDROID_APP_SPEC.md) · [Builder spec](BUILDER_SPEC.md). `[S#]` links in [README](README.md#evidence-register).

## Latest verified baseline — 4 November 2026

| Evidence tier | Verified outcome | Still unverified |
|---|---|---|
| User-supplied physical Android observation | E0/E1 managed/protected launcher fixture passes all eight expected exits on OPPO CPH2819 Android 16/API 36, ARM64, 4 KB, at the recorded original APK revision | Applicability to newer launcher, APKs, devices and page sizes |
| Host unit/negative regressions | At PR #3 head: 27 app/native, 6 shared/evidence, 9 builder tests pass in GitHub Actions | Android OS and OEM semantics |
| Clean source build and static contract | Nine source packages, source provenance, Python producer/verifier and production Java consumer pass; bootstrap and source bundle published | Android linker loading, child execution, network/SSH behavior |
| APK assembly and lint | Proof, terminal and instrumentation APKs built; [PR #3 CI](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863) passed 4/4 jobs | Installed terminal behavior; device instrumentation never run |
| E2/E3 and release | Neither E2 nor E3 has an Android device PASS | E2 system-linker/process semantics, E3 real GH → Git → SSH, Android terminal, 16 KB/OEM/API matrix, security and distribution approval |

**Required progression:** E0/E1 fixture result → E2 device acceptance with the actual matching APK/source digest → terminal/PTY/bootstrap and source-built Bash/Git/OpenSSH device acceptance → source-build GH and test real E3 → Python/Node runtime subprocess tests → T19–T21 release gates. A separate T05 child fixture is not a substitute for real E3. Keep `NOT RUN` until actual device logs exist, and retain source/APK hashes, API/ABI/page-size/targetSdk, expected and actual exits, and a redacted log. Host/static PASS and device PASS are distinct.


## 1. Verification rules

| Plain language | Engineering rule |
|---|---|
| A good-looking diagram is not proof. | Source evidence establishes a mechanism, not success for our specific build, target SDK or Android device. |
| When something has not been tested, say so. | Results are recorded as `PASS`, `FAIL`, `NOT RUN` or `BLOCKED` with evidence location and test environment. |
| Prove the risky bit before building more. | E1/E2/E3 are architecture acceptance gates, not final QA polish. |
| One failure must not corrupt a working installation. | Archive validation, staging, rollback and crash-recovery tests are mandatory. |
| A package should work with other packages. | Nested execution, argument preservation, libraries and interpreter behavior are integration tests. |

## Recorded device evidence

[E0/E1 OPPO fixture record](docs/evidence/oppo-cph2819-api36/README.md): user-supplied output on CPH2819 / Android 16 / API 36 / targetSdk 36 / ARM64 / 4096-byte pages. E0 PASS and E1 PASS **only for that device and fixture**; all eight expected case exits match. APK hash and source merge commit `c54afee` were checked before attribution. The log is not signed or cryptographically bound to the APK and contains no timestamp. E2 and E3 NOT RUN; 16 KB and broader compatibility NOT RUN.

The scenarios below remain requirements. Host, build and device results must be reported separately; a configured workflow is not device evidence.

## 2. Environment and artifact identity

Every test result MUST record: app git revision, builder git revision, toolchain lock revision, package manifest digest, ABI, OS/API, targetSdk, page size (4 KB/16 KB), Android build fingerprint or emulator image, `APP_ID`, `$PREFIX`, execution route used, exact command, exit code, and location of sanitized output logs. Redact user tokens, private keys, device identifiers not needed for debugging and personal paths.

Minimum matrix proposal: arm64 Android API 30, a current supported Android release, current Play-required target API configuration, and at least one 16 KB page-size device/emulator. Include vendor physical hardware before declaring production readiness. A successful API 30 emulator test does not prove Android 16 or Play-target behavior. [S9][S12]

## 3. Highest-priority architecture gates

| Gate | Setup / action | Expected result | Failure decision |
|---|---|---|---|
| **E0**: Native packaging | Build executable ELF named `libtp-launcher.so`; install/extract app as configured. | Android discovers an actual executable path in nativeLibraryDir; ABI, mode and ELF entry are correct. | Reject packaging assumption; investigate supported native install/extraction mechanics. |
| **E1**: Command shortcut | Create writable `$PREFIX/bin/gh` symlink to protected launcher; call via `execve` with controlled `argv[0]`. | Symlink target launches; launcher reliably discovers `gh` from verified invocation path, even with spoofed argv0. | Reject/replace ADR-004; do not claim multi-call scheme works. |
| **E2**: Bionic target load | Launcher passes a known, compatible dynamic ELF with quoted/empty args to `/system/bin/linker64`. | Exact argv, env, stdin/out/err, exit code, cwd and signals preserved; no lingering launcher. | Fix launcher, package build, or select tested alternate launch mechanism. |
| **E3**: Nested launch | Bash launches source-built GH; GH launches Git; Git launches SSH using managed PATH. | Every step starts without Bash intercepting the child process. | Patch package call sites or change execution strategy; explicit limitation if unsupported. |
| **E4**: Fixed prefix | Build target with chosen `APP_ID` and canonical `$PREFIX`; install on actual app. | All compiled file/data/interpreter paths resolve; no `com.termux` or host paths remain. | Fail recipe; do not fake relocation. |
| **E5**: Release channel | Compare actual distribution behavior with current Play policies. | An approved and documented Play feature set; no forbidden external native executable fetching. | Block Play release; define another distribution mechanism before introducing downloads. |

**Source context:** Android direct-exec restriction [S1]; Termux exec approach [S2]; Bionic linker implementation [S16]; native library packaging [S10]; Google Play distribution rules [S13]. The exact E1 shortcut mechanism is an **inference** requiring test, not a stated guarantee of those sources.

### Required probes in E1/E2

- Invoke `gh` by basename, absolute shortcut path, `execv`, `execve`, `execvp`/`posix_spawn` where available, and a Go program using raw child execution.
- Set `argv[0]` to a misleading value. Confirm executable routing never relies on attacker-controlled argv0 alone. Check if `AT_EXECFN` contains the symlink path and when it changes under Android kernels.
- Launch with arguments `""`, `"a b"`, `"--"`, multibyte Unicode and nested shell quoting; require byte-preserving argument vector.
- Test environment variables, cwd, process group, inherited FDs, pipes, Ctrl+C, SIGTERM and exit statuses (0, 1, 127, killed by signal).
- Prove no recursion when command shortcut and `tp-real` target names collide; test broken, circular and swapped symlinks.
- Verify correct dynamic libraries and namespace behavior; no broad unsafe fallback that could load attacker-controlled `.so` unexpectedly.

## 4. Builder tests

| Test | Positive criterion | Negative / failure criterion |
|---|---|---|
| Pinning | Same lockfiles accepted locally and in clean CI | Tag changes or hash mismatch cause hard failure |
| Dependency closure | Build entire required target dependency graph from upstream sources | Detect cycles, missing dependencies and precompiled target dependency downloads |
| Patch provenance | Known patch applies to pinned version; attribution recorded | Unreviewed/incompatible patch blocked |
| ELF static inspection | ELF64 AArch64, dynamic format, page-size alignment, valid DT_NEEDED | Reject static/foreign ABI/host prefix/misaligned PT_LOAD |
| File inventory | Every payload file has path, hash, role, owner | Duplicate path, special file, missing asset rejected |
| Source/toolchain | Version and digest stamped in provenance | Environment drift or mutable release input rejected |
| Local/CI parity | Same build entry point with equivalent locked inputs | Divergent hidden build flags blocked |
| Package integration | Bash, Git, SSH, Python/Node/GH paths exercised on Android | Library and child-launch failures block release |
| Release | Attestation and license inventory attached to passing artifacts | `NOT RUN` device test cannot be turned into PASS by CI configuration |

The absence of a claimed reproducibility guarantee is deliberate: byte-identical builds are optional only after a measured double-build comparison. Do not claim that pinned sources alone prove reproducibility. [S5][S7][S11]

## 5. App and terminal tests

| Scenario | Expected observable result |
|---|---|
| First launch | Bootstrap verifies, shell prompt appears, no external native package fetch |
| Empty/corrupted bootstrap | Clear error; no silent download or destroyed user home |
| Input/output | Ctrl keys, Unicode, ANSI output, scrollback and keyboard handling work |
| PTY control | Ctrl+C interrupts foreground job, resize triggers SIGWINCH, `stty size` tracks dimensions |
| Bash shell semantics | Pipelines, redirection, `exit`, background `&` and job control work |
| App lifecycle | Rotation/background/stop behavior matches documented policy; process cleanup works |
| Nested child | `gh -> git -> ssh`, Python `subprocess`, Node `child_process`, script interpreter paths |
| Libraries | Missing dependency yields diagnostic; correct package-local/shared libraries loaded |
| Storage | `$HOME` preserved through app update and interrupted installation |
| Accessibility | IME, screen-reader naming and keyboard access pass manual checks |

## 6. Edge cases and resolution plan

| Edge case | Severity | Required resolution / evidence |
|---|---|---|
| Protected native library not extracted to executable filesystem | Critical | E0 failure changes packaging approach; no assumption that `.so` file name makes ELF runnable. |
| Writable symlink cannot launch protected target or loses invoked name | Critical | E1 failure triggers architecture reconsideration, not another opaque layer. |
| Child program uses absolute writable ELF path | High | Package-build patch or explicit managed-entry route; negative test proves default fails safely. |
| Go raw `execve` bypasses preload | High | PATH-managed entry or targeted patch; no universal `LD_PRELOAD` claim. [S15] |
| Static binary / unsupported interpreter | High | Exclude, rebuild dynamically if possible, or revise contract after a new tested route. |
| Script with nested shebang or `/bin/sh` | High | Build-time interpreter rewrite and explicit invocation test; enforce bound on recursion. |
| External path traversal or symlink archive entry | Critical | Validate normalized path and resolved destination before staging; reject entire archive. |
| Cross-package command/file collision | High | One active provider and explicit ownership; fail if ambiguous. |
| Source checksum mismatch / upstream compromise | Critical | Fail closed, quarantine source, require manual review and repinning. |
| Package update killed halfway | Critical | Transaction journal and rollback; simulate process death during each install step. |
| Runtime packages share same app UID | High | Treat as one trust domain; no claim that launcher makes package files immutable. |
| Android background process restriction | Medium | Document supported lifecycle; verify on physical device; no indefinite-run promise. |
| 16 KB page-size incompatibility | High | Builder ELF validation + emulator/device load tests. [S9] |
| Google Play executable download restriction | Release blocker | No Play build fetching executables outside Google Play unless policy-compliant delivery demonstrated. [S13] |
| Nmap privileged/raw sockets | Capability blocker | Document supported nonprivileged functionality; no root claims. |
| Signature present but package vulnerable | High | Security review independent of provenance; track advisories, patch decisions and license compliance. |

## 7. Security gates and adversarial tests

**Threat model:** Untrusted archive metadata and contents, compromised upstream tarball/patch, malicious dependency or package code, symlink races, privilege confusion at command launch, installed package tampering, secrets in logs and release pipeline injection. Native programs in one app UID share a trust boundary; no per-package runtime isolation exists by default.

Required checks:

1. **Supply chain:** immutable source revision + checksum/signature where provided; pinned build dependencies, least-privilege CI, no secrets on untrusted forks; provenance records. [S11]
2. **Archive import:** reject `../`, absolute paths, traversal after normalization, symlink redirection, duplicate names, external hardlinks, devices, malformed tar, oversized extraction, excessive nested entries, and unreviewed install hooks.
3. **Path validation:** allowlisted root and relative package paths, safe resolution, descriptor/no-follow operations where possible; avoid time-of-check/time-of-use races on mutable directory trees.
4. **Launcher:** command registry ownership and path checks, bounded argument sizes, no recursive self-launch, deliberate environment sanitization only where required, no shell-string interpolation.
5. **Tampering:** verify signed package metadata and file hashes at installation or requested diagnostic checks; document that writable package files can change between checks and execution.
6. **Privacy:** no collection of terminal contents by default; no sensitive CLI arguments, tokens or private keys in telemetry and CI logs.
7. **Distribution:** current Google Play policies reviewed for actual APK behavior and any later import/download capability. [S13][S14]

## 8. Falsification / fallback decision tree

```text
Can app launch a protected native launcher (E0)?
  NO -> redesign how executable native entry is packaged
  YES
    |
Does PATH symlink reach launcher and preserve command identity (E1)?
  NO -> drop multi-call shortcut assumption; compare explicit linker command
        entry points versus tested Termux-style interception and source patches
  YES
    |
Does launcher run compatible ELF with correct process semantics (E2)?
  NO -> investigate Bionic contracts, packaging and linker/env semantics
  YES
    |
Do nested commands work (E3)?
  NO -> inspect exact child invocation, patch controlled package or reconsider
        architecture if widespread; do not claim a universal interception solution
  YES -> freeze command contract and proceed with package ecosystem
```

Fallback MUST be evaluated against total number of package changes, number of protected native artifacts, compatibility matrix and demonstrable child-launch coverage. Do not automatically add both an interceptor and a launcher “for flexibility.”

## 9. Quality bar and release-blocking criteria

- 100% of **critical execution gates E0–E4** have recorded, reproducible PASS evidence for supported device families before runtime design is called finalized.
- Every exported command has a manifest declaration and at least one successful positive launch probe plus required negative probes.
- No known unresolved critical package-import path escape, signature bypass, corrupted rollback or arbitrary target execution vulnerability.
- No release if architecture-specific test is FAIL/BLOCKED or if a claimed mandatory device result is NOT RUN.
- All builder release inputs are pinned and every prebuilt target package dependency is prohibited.
- No unapproved changes to the shared package schema once builder and app are integrating; schema changes require versioning and both consumers' tests.
- Documentation for errors, scope limits, update and repair operations exists before release.
- Release report lists exact supported Android API/ABI/page-size combinations and known unsupported package features.

These thresholds are **proposed baseline constraints** pending project-owner review. They are requirements for future engineering, not results achieved in the documentation phase.

## 10. Evidence log template

```text
TEST ID: E1-SYMLINK-ARM64
STATUS: NOT RUN | PASS | FAIL | BLOCKED
DATE:
APP / BUILDER REVISIONS:
ANDROID API / targetSdk / page size / fingerprint:
APP_ID / PREFIX / nativeLibraryDir:
BINARY SHA256 + ELF INSPECTION:
COMMAND + EXPECTED RESULT:
ACTUAL EXIT CODE + OBSERVATION:
SANITIZED LOG PATH:
FAILURE ANALYSIS / FOLLOW-UP ADR:
REVIEWER:
```

**Evidence status:** the scoped E0/E1 record above is filled. Remaining tests require actual records; do not generalize this fixture to universal compatibility or completed release gates.
