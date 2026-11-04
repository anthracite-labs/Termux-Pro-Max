# Termux Pro — Dependency-Ordered Implementation Plan

**Status:** engineering plan baseline; current implementation and evidence are tracked in [EXECUTION_STATUS.md](EXECUTION_STATUS.md).
**Gating philosophy:** validate minimal E0/E1 and E2 fixtures early, then prove the real source-built GH → Git → SSH chain (E3) once its builder, packages and terminal prerequisites exist. Independent builder and UI work may continue with device gates open. **No speculative package manager, custom linker, modified Bash or multi-ABI support.**  
**Sources and references:** [README](README.md#evidence-register) · [Architecture](ARCHITECTURE.md) · [App](ANDROID_APP_SPEC.md) · [Builder](BUILDER_SPEC.md) · [Contract](PACKAGE_CONTRACT.md) · [Verification](VERIFICATION.md).

## 1. Capability map

| Module ID | Responsibility | Dependency |
|---|---|---|
| `foundation` | Freeze target assumptions, app ID, trusted sources, acceptance gates | None |
| `exec-proof` | Validate native executable packaging, symlinks, linker, child launch | foundation |
| `package-contract` | Freeze archive/manifest command rules, validation vectors | foundation + proof feedback |
| `source-builder` | Source fetch, verify, patches, cross-compile, package artifacts | package-contract |
| `terminal-app` | App UI, PTY, session lifecycle, bootstrap/import | exec-proof + package-contract |
| `core-packages` | Git, SSH, Python, Node, GH in proven runtime | source-builder + terminal-app |
| `release-hardening` | Security checks, tests, release provenance, policy review | all modules |

Dependency direction is one-way: the builder outputs packages conforming to `package-contract`; the app consumes them; runtime integration tests validate the boundary. No builder-to-app runtime callback service or circular runtime dependency is allowed.

## 2. Work phases and stop gates

| Phase | Plain language | Technical exit condition |
|---|---|---|
| 0: Approve baseline | Pick the app identity and what Android phones we support. | Review docs, freeze `APP_ID`, ABI, minSdk, targetSdk, prefix and exact native execution candidates; signed-off requirements. |
| 1: Prove execution fixtures | Test protected ELF identity, managed symlinks, dynamic linker and controlled child-process behavior on Android. | E0/E1 and E2 Android fixture evidence or explicit blockers; **real E3 is a Phase 4 gate**. |
| 2: Build factory | Source-build Bash in a clean repeatable environment. | Builder passes pinned-source checks and produces a contract-valid Bash package locally and in CI. |
| 3: Ship minimal terminal internally | Run our Bash from our app with real keyboard and PTY. | Interactive session, signals, jobs and package import tests PASS. |
| 4: Expand ecosystem | Build and run integrated packages. | Real Android GH → Git → SSH (E3), Python subprocess and Node child_process probes pass after their source-built packages exist. |
| 5: Harden and prepare distribution | Avoid broken updates and unsafe package imports. | Security/rollback/API/page-size tests PASS; policy gate E5 reviewed for chosen release. |

**Important sequencing note:** E0/E1 and E2 use minimal NDK fixtures. T05 is a child-process **fixture**, not real E3; T17 is real GH → Git → SSH. Source builds, package contract and terminal UI can be developed in parallel after defining the candidate interface. A candidate ADR does not imply device acceptance or release approval.

## 3. Verifiable task backlog

Tasks are scoped so a future agent can implement and verify each task in a focused session. Tests and commands are **planned**, not already present.

### Foundation

**T01 — Freeze product and Android target.** Decide unique application ID, package namespace, ABI (`arm64-v8a`), minimum Android/API, Play targetSdk, package prefix and release channel. **Acceptance:** decisions recorded, all docs consistent; any deviation requires ADR. **Verify:** config diff review against README source registry. **Depends on:** none.

**T02 — Capture current authoritative source baseline.** Pin source URLs/commits and official docs for Android W^X, Bionic, native APK libraries, Termux Play exec/packages, NDK, Play rules and 16 KB pages. **Acceptance:** every decision labeled source-proven, inferred or test-pending; no broken source links. **Verify:** manual link/specific-claim review. **Depends on:** T01.

**T03 — Write the executable path proof harness.** Define a minimal Android Activity/harness and NDK ELF fixtures to test protected extracted native ELF and writable shortcut behavior. **Acceptance:** reproduces E0/E1 with adversarial `argv[0]` inputs. **Verify:** emulator run + actual device output. **Depends on:** T01,T02.

**T04 — Validate Bionic launch semantics.** Test exact linker invocation and argument/env/FD/exit/signal behavior with dynamic fixture. **Acceptance:** E2 PASS or documented failure/fallback; static ELF negative test rejected. **Verify:** Android command output + process observations. **Depends on:** T03.

**T05 — Validate a minimal child-process fixture.** Construct a C or Go fixture invoking registered Git-like test commands through managed paths. **Acceptance:** device-side positive and negative process-launch behavior documented; this fixture is not the real source-built E3 chain. **Verify:** Android trace and exit status. **Depends on:** T04.

**T06 — Track and eventually freeze execution ADR.** Compare tested paths with Termux `termux-exec`, wrappers and direct linker options. **Acceptance:** provisional candidate for implementation; final ADR-004 approval only after real Android E2 and T17/E3 evidence. **Verify:** architecture review. **Depends on:** T03–T05 provisionally; T17 for final approval.

### Builder and package contract

**T07 — Freeze shared manifest and archive format.** Make schema version, hash envelope, command exports, dependency fields, owner index and app prefix concrete; include invalid fixture cases. **Acceptance:** sample accepted/rejected cases documented and two consumers share fixtures. **Verify:** schema conformance tests. **Depends on:** T01,T03; T06 may remain provisional.

**T08 — Pin toolchain and upstream build backend.** Select Android NDK, host environment digest and exact reviewed Termux tooling; lock inputs. **Acceptance:** clean `doctor` validates pins; no unreviewed downloads of prebuilt target packages. **Verify:** clean local and CI environment checks. **Depends on:** T07.

**T09 — Build from upstream sources.** Implement fetch/hash/signature check, patch application and dependency-closure compile for Bash. **Acceptance:** source provenance and dependency graph recorded; no target dependency binary downloads. **Verify:** negative hash test and clean build logs. **Depends on:** T08.

**T10 — Validate and package Bash.** Stage canonical prefix files, inspect ELF/PT_LOAD/DT_NEEDED, emit package manifest and archive. **Acceptance:** package contract passes; wrong prefix/ABI/static and missing dependency fixtures fail. **Verify:** static package verifier and emulator load test. **Depends on:** T09.

**T11 — Local and GitHub Actions parity.** Run same builder entry point with locked versions, separate release permissions, attach logs/hashes/provenance. **Acceptance:** local+CI artifacts are both validated; divergence explained, not silently accepted. **Verify:** clean CI run and reviewed job logs. **Depends on:** T10.

### Android app

**T12 — Minimal terminal screen.** Implement accessible terminal view with keyboard, Unicode and ANSI output; use reviewed existing terminal rendering where justified. **Acceptance:** representative manual/screenshot checks and input events PASS. **Verify:** UI automation / accessibility review. **Depends on:** T01.

**T13 — PTY/session bridge.** Open PTY, launch shell via chosen route, handle I/O, SIGWINCH, Ctrl+C, process groups and exit. **Acceptance:** job control, resize and signal tests pass on Android. **Verify:** emulator/device session trace. **Depends on:** T03,T07,T12; E2 Android acceptance remains a runtime gate.

**T14 — Bootstrap and package installation.** Implement staged verified extraction, manifest/ABI/prefix checks, generated managed commands, rollback journal and repair. **Acceptance:** bundled Bash package imports and survives interrupted installation without deleting HOME. **Verify:** corrupted archive, wrong ABI, path traversal, crash-injection tests. **Depends on:** T07,T10,T13.

**T15 — App integration acceptance.** Run compiled Bash from installed app and confirm command path/PTY/lifecycle. **Acceptance:** normal shell, Ctrl+C, pipe/background, rotation and exit behavior PASS. **Verify:** Android instrumentation and manual tests. **Depends on:** T13,T14.

### Core packages and release

**T16 — Git and OpenSSH recipes.** Build pinned upstream sources and dependencies; patch child paths, TLS/cert/config references. **Acceptance:** Git local repository and Git-to-SSH process launch tests PASS. **Verify:** source recipe logs + Android test. **Depends on:** T09,T10 for source-build implementation; T15 for Android acceptance.

**T17 — GH package and nested launch.** Source-build GitHub CLI; verify GH invokes installed Git via managed PATH, then Git launches SSH. **Acceptance:** full GH→Git→SSH trace E3 PASS. **Verify:** Android integration test with controlled local fixtures where possible; no production credentials. **Depends on:** T16,T15 and successful Android E2 behavior.

**T18 — Python and Node.js packages.** Source-build required runtime and dependencies; preserve data/stdlib/npm assets. **Acceptance:** Python `subprocess` and Node `child_process` launch Git via managed PATH; imports and resource files work. **Verify:** Android runtime tests. **Depends on:** T11 for source-build implementation; T15 for Android acceptance.

**T19 — Import/update hardening.** Verify archive authenticity policy, ownership, atomicity/recovery, path escapes and shared-UID risk. **Acceptance:** no outstanding critical exploit paths in defined importer model; rollback tests PASS. **Verify:** negative fixtures + threat review. **Depends on:** T14,T17,T18.

**T20 — Compatibility and channel gate.** Exercise current Android/target SDK matrix, 4 KB/16 KB page sizes, physical OEM device, and Google Play distribution behavior review. **Acceptance:** exact supported matrix and legal distribution mechanism documented; no forbidden claim of remote executable downloads. **Verify:** tested device logs and policy review signoff. **Depends on:** T17–T19.

**T21 — Release-readiness decision.** Review all tests, ADRs, licenses, missing features, provenance and unsupported cases. **Acceptance:** decision marked READY / NOT READY with evidence, not assumptions. **Verify:** gate checklist and release candidate audit. **Depends on:** T20.

## 4. Dependency order and parallel work

```text
Foundation:    T01/T02 → T03 E0/E1 → T04 E2 fixture → T05 child fixture
Contract:      T01 + T03 → T07 → T08 → T09 → T10 → T11 CI
Terminal:      T01 → T12 UI; T03 + T07 + T12 → T13 PTY
Bootstrap:     T07 + T10 + T13 → T14 → T15 Android acceptance
Core builder:  T09 + T10 → T16 Git/OpenSSH source builds
Core device:   T15 + T16 + Android E2 → T17 GH → Git → SSH real E3
Runtimes:      T11 → T18 Python/Node source builds; T15 → runtime tests
Release:       T14 + T17 + T18 → T19 → T20 → T21
```

Task-level acceptance requirements take precedence over the simplified diagram. **Fixture E0/E1 and E2 tests are not E3.** The first real nested GH → Git → SSH acceptance requires the actual source-built packages and Android app. Builder recipes and UI may progress while device-specific results remain pending; final architecture approval and release may not.

**Merged baseline (4 November 2026):** PRs #1, #2 and #3 have been merged into `main`. The nine-package Bash/OpenSSH/Git source-build closure, bundled terminal and automated host/build jobs exist. Device-side E2, Android app acceptance, E3, Python/Node and release gates remain open; see [EXECUTION_STATUS.md](EXECUTION_STATUS.md).

## 5. Implemented repository boundaries

```text
termux-pro-builder/       toolchain/source locks, recipes, scripts, tests, CI
termux-pro-app/           Android Gradle app, terminal/PTY, native launch proof
shared/                  package schema + conformance fixtures if both projects share source
```

These modules and the `./build.sh` entry point now exist. Their presence proves implementation, not Android runtime compatibility. All new packages must continue to comply with the shared package contract and release acceptance gates.

## 6. Deliberately postponed work (Ponytail)

- No fork of Bash just to implement runtime command resolution.
- No permanent launcher daemon, custom ELF loader or generic shell-script launcher for every package.
- No full dependency solver / apt-like package manager in version one.
- No dynamic remote package repository for the Play app until distribution policy approves its mechanics.
- No Docker/root/kernel emulation, extra CPU architectures, cloud build service, UI design system or automatic package discovery.
- No guarantee that arbitrary external binaries, scripts with fixed shebangs or raw absolute `execve` will work.

## 7. Definition of done for future code

1. Every task has a test that can fail for a real defect and clear evidence when it passes.
2. Source references, decisions and package contract remain consistent.
3. Build commands run from a clean checkout with locked inputs; unavailable tests recorded `NOT RUN`.
4. Runtime claims are backed by Android emulator/device evidence, not only host-side ELF inspection.
5. No unreviewed critical security/regression defect or bypass of signed package integrity rules.
6. No unnecessary abstraction survives final review when simpler platform or upstream functionality exists.

## 8. Historical documentation-phase exit criteria

- [x] Seven Markdown files with cross-links and defined ownership.
- [x] Single shared package/command contract documented; app and builder defer to it.
- [x] All high-risk architecture assumptions identified as **unverified**.
- [x] Explicit implementation tasks, dependencies, acceptance criteria, testing and fallback decisions.
- [x] Source register and attribution policy included.
- [ ] Human has reviewed and approved the blueprint.
- [ ] Android device tests have passed (intentionally **out of scope** for this phase).

**Final deliverable of this phase:** the seven Markdown files bundled as `Termux-Pro-Engineering-Blueprint.zip`. Not a runnable Android app or builder implementation.
