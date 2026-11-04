# Termux Pro — Engineering Blueprint

**Edition:** documentation baseline v0.1  
**Prepared:** 3 November 2026  
**Status:** PRs #1–#3 merged to `main` (4 November 2026); source builder and bundled terminal candidates implemented; OPPO E0/E1 fixture-specific PASS; Android E2/E3/terminal acceptance and release pending.
**Input:** `Termux_Pro_Architecture_Report.md` supplied by the project owner  
**Scope:** documentation for a standalone package builder and a new Android terminal application; not a fork of existing Termux.

Implementation progress is tracked in [EXECUTION_STATUS.md](EXECUTION_STATUS.md).
The first runnable experiment is the [Android E0/E1 execution harness](termux-pro-app/README.md);
the [standalone source builder](termux-pro-builder/README.md) now builds a candidate Bash/ncurses/readline bootstrap locally. A bundled-Bash Android terminal candidate is implemented; physical-device acceptance remains outstanding. The publication-time statements
below describe the original documentation baseline.

## Current repository implementation

The original seven-file blueprint is the requirements baseline. The merged repository also contains `termux-pro-builder/`, `termux-pro-app/` and `shared/`: a pinned source-build system capable of producing nine candidate packages through Git, a bundled-source terminal APK and instrumentation test APK, and automated host/build/static checks. [Exact-head CI evidence](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863) applies to PR #3, not automatically to future commits or Android execution. Do not confuse an APK artifact with device acceptance.

**Next gates:** Android E2, source-built Bash/PTY/bootstrap/Git/SSH runtime tests; source-built GH and real GH → Git → SSH E3; Python/Node; security, page-size/device matrix, distribution and release decisions. Current statuses and merge SHAs are in [EXECUTION_STATUS.md](EXECUTION_STATUS.md). See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the corrected execution order.


## Read this first

| In plain language | In engineering language |
|---|---|
| Our own factory builds the tools. | Builder obtains pinned upstream source, applies reviewed Android patches, compiles the dependency closure, verifies outputs, and publishes package artifacts. |
| One Android app runs those tools. | Termux Pro provides a terminal/PTY and a controlled package runtime rooted at the app-private `$PREFIX`. |
| Android needs a safe doorway to start programs stored in writable directories. | Android 10+ target-SDK restrictions prohibit ordinary direct `execve` from writable app home; we must verify an Android-compatible execution route. [S1][S2] |
| Bash stays Bash. | Upstream Bash is a normal package; it is not patched into a general-purpose resolver. |
| We test a small end-to-end chain before expanding. | Critical first acceptance gate is protected-launcher execution, symlink identification, `linker64` launch, and nested `gh -> git`. |

**Decision status:** `PROPOSED` means an architecture choice supported by reasoning and cited sources but not yet device-proven. `VERIFIED-UPSTREAM` means the cited upstream documentation/source establishes the *mechanism*, not that our implementation has passed. `BLOCKED` means a missing decision or test prevents approval. We do not call the design production-proven.

## Document map

| File | Purpose / output of Agent Skills |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Capability map, topology, decisions, evidence, alternatives, architecture gates (source- and doubt-driven review / ADRs). |
| [BUILDER_SPEC.md](BUILDER_SPEC.md) | Requirements and interfaces for the standalone local/CI source-build system (spec-driven development). |
| [ANDROID_APP_SPEC.md](ANDROID_APP_SPEC.md) | Requirements, session lifecycle and launcher/PTY contracts for the Android app (spec-driven development). |
| [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md) | Single normative contract shared by the builder and the app: paths, package format, runtime invocation and dependencies. |
| [VERIFICATION.md](VERIFICATION.md) | Risk register, threat model, proof matrix, acceptance criteria and release blockers (doubt- and constraint-driven development). |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Dependency-ordered engineering tasks, verification commands to implement and stopping gates (planning and task breakdown). |

These seven documents are the **final deliverable for this documentation phase**. They intentionally contain no executable implementation and no claims of passing device tests.

## Scope and defaults

| Area | Working decision | Status |
|---|---|---|
| Product | Brand-new Android terminal named *Termux Pro* | Project requirement |
| Device architecture | `arm64-v8a` only in the first proof | Proposed; reduces matrix |
| Minimum Android | Android 11 / API 30 initial target | Proposed, aligned to Google Play Termux's stated minimum [S6] |
| Play target API | API 36 or higher for submissions as of 3 Nov 2026 | Verified-current requirement [S12]; recheck at submission |
| Source policy | First-party package binaries must be built in our pipeline from pinned upstream source; host compilers/SDKs are pinned, not recompiled from scratch | Project requirement / clarification |
| Package family | Bash first; Git/SSH/Python/Node/GH later; Nmap/FFmpeg/Go gated separately | Proposed sequencing |
| Distribution | Initial APK bundles a verified bootstrap. External runtime package delivery **not approved** for the Play variant pending policy review | Proposed / explicit release gate [S13] |
| Android application ID | **Not chosen**. A unique `APP_ID` must be fixed before release package builds. | BLOCKED for full package release |
| Native execution | Proof candidate: extracted protected launcher + managed PATH symlinks + Bionic `linker64`; alternative documented if it fails | PROPOSED / BLOCKED pending device test |

**Important trust distinction:** We build target packages from official sources; using an NDK, compiler, container image, or GitHub runner still means trusting those pinned build tools. “Built by us” is not synonymous with reproducible, audited, or harmless. [S7][S11]

## Source-of-truth rules

1. Use the **upstream source** for the package's implementation. Use official Android documentation for platform behavior, and the Google Play Termux sources as a *porting reference*, not an upstream binary vendor.
2. Use [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md) for every builder-to-app interface. Do not create conflicting package schemas in app and builder documents.
3. Treat package prefix paths, launcher ABI/entry-point semantics, and Play distribution as **release gates**, not guesses.
4. Adopt the smallest design that passes the required tests. Do not implement a custom ELF loader, a Bash fork, a package manager, or universal binary interception without an observed need.
5. If an acceptance test fails, update the corresponding decision in [ARCHITECTURE.md](ARCHITECTURE.md) before implementing a workaround.

## Evidence register

URLs below are primary documentation or upstream project sources checked while drafting this blueprint. References `[S#]` are used consistently throughout the bundle.

- **S1 — Android W^X execution restriction:** https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission
- **S2 — Google Play Termux `termux-exec` source and limitations:** https://github.com/termux-play-store/termux-exec/blob/main/README.md
- **S3 — Google Play Termux app source:** https://github.com/termux-play-store/termux-apps
- **S4 — Google Play Termux package recipes:** https://github.com/termux-play-store/termux-packages
- **S5 — Upstream Termux package build guide / `-i`, `-I`:** https://github.com/termux/termux-packages/wiki/Building-packages
- **S6 — Google Play Termux project page / status / Go fixes:** https://github.com/termux-play-store
- **S7 — Official Android NDK for upstream build systems:** https://developer.android.com/ndk/guides/other_build_systems
- **S8 — Termux prefix layout:** https://github.com/termux/termux-packages/wiki/Termux-file-system-layout
- **S9 — 16 KB native-page compatibility:** https://developer.android.com/guide/practices/page-sizes
- **S10 — Android packaging of native libraries:** https://developer.android.com/guide/topics/manifest/application-element
- **S11 — GitHub artifact attestations and their limits:** https://docs.github.com/en/actions/concepts/security/artifact-attestations
- **S12 — Google Play target API requirements:** https://developer.android.com/google/play/requirements/target-sdk
- **S13 — Google Play device and network abuse / downloaded executable policy:** https://support.google.com/googleplay/android-developer/answer/16559646
- **S14 — Android dynamic-code security:** https://developer.android.com/privacy-and-security/risks/dynamic-code-loading
- **S15 — Upstream Go raw child execution:** https://go.dev/src/syscall/exec_linux.go
- **S16 — Android Bionic linker source:** https://android.googlesource.com/platform/bionic/+/main/linker/linker_main.cpp
- **S17 — Termux execution environment and PATH pitfalls:** https://github.com/termux/termux-packages/wiki/Termux-execution-environment
- **S18 — Termux package build configuration / fixed app prefix:** https://github.com/termux/termux-packages/blob/master/scripts/properties.sh
- **S19 — Termux bootstrap packaging pattern:** https://github.com/termux/termux-packages/wiki/For-maintainers
- **S20 — Go Play Termux release history:** https://github.com/termux-play-store/termux-apps/releases

### What the source report did not prove

The original report proposed a symlink in writable `usr/bin` to a protected native launcher and assumed it could identify the invoked command reliably. Neither the report nor upstream documentation supplies an on-device test of **our exact mechanism**. That claim remains conditional in every specification. Likewise, no user-supplied implementation repository, CI log, compiled ELF, Android test log, or package-signing key was provided.

### How to consume the blueprint

Read `ARCHITECTURE.md` → `PACKAGE_CONTRACT.md` → the two product specifications → `VERIFICATION.md` → `IMPLEMENTATION_PLAN.md`. Build should not start until the first architecture gate has a falsifiable test and a defined fallback. The project owner may approve these documents as the planning baseline; approval is not evidence that the runtime works.
