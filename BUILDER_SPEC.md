# Termux Pro Builder — Implementation Specification

**Status:** implemented source-builder candidate on `main`; **release acceptance is incomplete**. See [EXECUTION_STATUS.md](EXECUTION_STATUS.md).
**Owner:** Termux Pro Builder project.  
**Inputs/outputs contract:** [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md).  
**Upstream references:** Termux package recipes [S4], build workflow [S5], Android NDK [S7], prefix configuration [S18] (URLs in [README](README.md#evidence-register)).

## Implementation alignment — merged checkpoint, 4 November 2026

The standalone `termux-pro-builder/` is operational for **nine source-built Android ARM64 packages**: ncurses, readline, Bash, zlib, OpenSSL, OpenSSH client, CA certificates, curl and Git. `./build.sh bootstrap bash openssh git` constructs one dependency closure and candidate `.tpkg` archives plus `bootstrap.zip` and corresponding-source bundle. GitHub Actions at PR #3 head `27e445b` completed all four jobs, including strict Python and production Java package consumers and packaging the same-run bootstrap into a terminal APK ([verified CI](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41769436863)).

Existing implementations enforce pinned source digests, signer identities where upstream detached signatures exist, zero-fuzz patches, fixed Android identity/prefix, ELF/DT_NEEDED/SONAME/RUNPATH checks, and package inventory. CA certificate input has a pinned hash/license but no upstream detached signature; upstream zlib has a legacy DSA/SHA-1 signature limitation. No opaque prebuilt Android target packages are used. An immutable host-image digest, release signing, license/security/policy sign-off, and full Android runtime checks remain open. Build/static PASS does **not** mean the Git/OpenSSH/Bash packages run on Android. Python, Node.js and GH are not implemented.

Do not weaken the original requirements to match this candidate implementation. Complete release gates before using the `release` entry point.


## 1. Mission

| Plain language | Technical requirement |
|---|---|
| Build our own versions of the programs from their maintainers' source code. | Build Android ARM64/Bionic target artifacts from pinned and verified upstream source and all target dependency sources. |
| Work on a Linux machine or GitHub Actions. | Use the same locked build entry point and inputs on both hosts. |
| Borrow useful Termux fixes, but do not trust their finished packages. | Vendor/pin reviewed recipes and patches with license attribution; disable any mode that downloads target package binaries from external package repositories. |
| Detect mistakes before publishing. | Fail closed on source-checksum mismatch, unsupported ELF, wrong prefix, missing dependency, unexpected files, command mapping collision and test failures. |

## 2. Scope and non-goals

**MVP:** source build, dependency resolution, package staging, static validation, package artifact packaging, local and CI build, bootstrapping Bash, minimal test ELF, and Git/SSH as follow-on test packages. **Not MVP:** source compiler bootstrapping, supporting all CPU ABIs, a public package repository, a complete dependency solver, automatic upstream updates, Nix/Bazel reconstruction, reproducibility guarantees we have not demonstrated, or arbitrary unreviewed packages.

One explicit command-line interface, conceptual contract:

| Command | Purpose | Required result |
|---|---|---|
| `./build.sh doctor` | Verify Linux host toolchain, pinned inputs and required disk/tool availability. | Nonzero exit if environment invalid. |
| `./build.sh build bash` | Build Bash plus entire target dependency closure from pinned sources. | Valid package archives or diagnostic. |
| `./build.sh build gh` | Build GH plus its pinned dependency closure. | Compatible target packages and command manifests. |
| `./build.sh bootstrap` | Compose a deterministic, verified first-run set of packages. | `bootstrap.tar.*`, manifest and content checksum. |
| `./build.sh verify <artifact>` | Inspect package archive against contract. | Machine-readable validation report and exit code. |
| `./build.sh test <package>` | Execute static checks and available Android integration test hooks. | PASS/FAIL with evidence; do not claim on-device PASS without device. |
| `./build.sh release` | Assemble signed/attested release artifacts only from passing builds. | Artifacts, hashes, provenance and license inventory. |

These commands are **specified**, not existing executable scripts. Exact compression format/implementation language remains an internal design choice; do not expand the interface casually.

## 3. Build layout — minimal repository

```text
termux-pro-builder/
  build.sh
  toolchain.lock
  sources.lock
  recipes/<pkg>/recipe.*
  patches/<pkg>/*.patch
  vendor/termux-build/      pinned upstream tooling or audited subset
  tests/
  .github/workflows/build.yml
  output/                   generated, never committed
```

Follow the existing Termux build engine where it applies. If adapting its scripts is cheaper than wrapping them in custom layers, keep the direct engine and make `build.sh` a thin entry point. Avoid an additional plugin system, package recipe DSL or bespoke orchestrator for one build backend.

## 4. Input verification and trust chain

1. **Locked upstream source:** `sources.lock` records project/repository URL, exact commit or release tag, release asset URL if applicable, SHA-256, optional upstream signature, and source license. Disallow mutable branches such as `main` as release inputs.
2. **Locked toolchain:** `toolchain.lock` records Android NDK revision + SHA, build host OS/image digest, language compiler/runtime versions (including Go/Rust/Node/Python when required), and reviewed Termux tooling commit. Use ARM64 Android target triple `aarch64-linux-android` with explicitly selected minimum API. [S7]
3. **Reviewed patches:** each patch has provenance URL/commit, original license, reason, target version and test identifier. Patches are treated as our source inputs, not blind downloads.
4. **No precompiled *target dependencies*:** upstream Termux `build-package.sh` defaults to source dependency builds unless `-i`/`-I` requests repo-built packages. Our release process MUST prohibit these switches and any equivalent dependency fetch path. [S5]
5. **Build-host tools:** pinned NDK/LLVM, Linux tools and language compiler binaries are trusted host tools, distinct from forbidden precompiled Android target packages.
6. **Controlled output:** exclude temporary files, developer secrets, host paths and unlicensed artifacts. Retain hashes, recipes, patch list, compiler inputs and logs.

A passing hash check confirms source bytes, not source integrity or license safety. Attestations prove origin/build context, not the absence of vulnerabilities. [S11]

## 5. Pipeline

```text
plan package graph
       |
check source & toolchain locks
       |
fetch pinned upstream tarballs/commits
       |
verify hashes/signatures (when available)
       |
apply reviewed patches in pinned order
       |
cross-compile target dependency closure for APP_ID/PREFIX
       |
stage payload into one virtual $PREFIX
       |
transform exported commands into launcher-compatible entries
       |
inspect ELF / dependencies / scripts / path references
       |
produce package manifest + archive + hashes + license inventory
       |
run emulator/device integration checks where available
       |
publish only after all required gates
```

### Build properties

- Target is initially **Android ARM64 (`arm64-v8a`)**, Android 11/API 30 minimum (provisional) and the current Play-required target API in app code; NDK API level and app target SDK are different settings.
- Build prefix is derived from fixed `APP_ID`, not copied from `com.termux`; do not mix packages built for different app IDs or prefixes. Termux documents precisely this behavior. [S18]
- A single `$PREFIX` layout is required: bin/lib/libexec/share/etc/var. Resolve `RUNPATH` and secondary library-loading requirements per package; do not assume `$ORIGIN` solves every dependency.
- ELF target files must be Android AArch64, dynamically linked where executable via system `linker64`, with compatible imports/SONAME/dependencies and **16 KB page-aligned segments**. Use the appropriate NDK (r28+ preferred) and check all .so and executable PT_LOAD alignment. [S9]
- Preserve package data: scripts, templates, Git exec-path helpers, Python standard library, Node/npm resources and certificates where needed.
- Record whether a command is a native ELF, interpreter script or helper; package format is specified once in [PACKAGE_CONTRACT.md](PACKAGE_CONTRACT.md).

## 6. Package recipe minimum

Each recipe must declare: package id, upstream project/release, source hash, license, pinned build dependencies, runtime dependencies, target ABI/API, build system, prefix patches, exported command(s), auxiliary data, and **integration probes**, including child-process behavior. No speculative recipe feature hooks until a second package requires them.

**Initial candidate matrix (gates, not delivery promises):**

| Package | Upstream authority | Build hazard | Required package probe |
|---|---|---|---|
| Bash | GNU Bash release at GNU mirrors | readline/ncurses/dependency paths, PTY behavior | interactive `bash -c 'echo ok'`, signal handling |
| Git | git-scm.com / git.git | HTTPS/TLS, libcurl, helper binaries, certificates | `git --version`; local repo; spawn SSH |
| OpenSSH | openssh.com / portable source | sandbox/socket restrictions, config paths | `ssh -V`; test key format and child invocation |
| Python | python.org / CPython | stdlib, extension modules, dynamic imports | import `ssl`, subprocess launching managed Git |
| Node.js/npm | nodejs.org / node repo | V8/toolchain, scripts, child_process | `node -e ...`; npm launches a managed command |
| GitHub CLI `gh` | cli.github.com / cli/cli | Go direct `execve`, networking, Git discovery | `gh --version`; GH invokes Git via PATH in controlled test |
| Nmap | nmap.org | privileged socket functionality | unprivileged supported scan; detect unsupported features |
| FFmpeg | ffmpeg.org | codec licensing/feature matrix | transcode simple test file |
| Go toolchain | go.dev | tool self-hosting and executable launch | `go version`; build+run dynamic Android test tool |

**Source authenticity:** recipe can reference official GitHub repositories maintained by upstream organizations, but do not automatically treat *any* GitHub mirror as authoritative. Exact URLs/tags and patch versions must be pinned during implementation, not fabricated in this spec.

## 7. GitHub Actions requirements

- Same `./build.sh` command as local builds; clean Linux runner or pinned container digest.
- Checkout and external actions pinned to immutable commits; minimal workflow permissions; do not run unreviewed PR-supplied source scripts with publish secrets.
- Separate `verify` and `release` jobs; upload tests even on failures; release only when source, package, emulator and policy gates pass.
- Build provenance and attestation where available; record toolchain hashes, complete source dependency graph and package hash. [S11]
- Do not download upstream Termux `*.deb`/`*.pkg.tar.*` to satisfy target dependencies.
- Android device tests are their own job and require an available emulator/device runner; a GitHub Actions workflow existing is not proof that tests ran.
- Ensure licensing and attribution accompany artifacts; stage source-offer obligations where licenses require them.

## 8. Failure modes and handling

| Failure | Required handling |
|---|---|
| Wrong hash / unexpected redirect / unsigned source where signature required | Abort source input; no fallback to an unpinned mirror. |
| Toolchain drift | `doctor` fails; do not silently upgrade NDK. |
| Dependency cycle | Show graph and cycle path; fail, do not choose arbitrary order. |
| Prebuilt target dependency attempted | Reject release pipeline with clear diagnostic. |
| Android prefix mismatch | Reject archive; never try to relocate using string replacement after release. |
| Unsupported static or non-AArch64 executable | Reject package for current launcher contract. |
| Missing `.so`, bad `RUNPATH`, unavailable symbol | Fail ELF/libraries check. |
| Executable command collision | Fail until an explicit provider is selected at install time. |
| 16 KB ELF segment misalignment | Fail; source-built binaries also need linker flags/toolchain verification. |
| Unreviewed license or patch provenance | Block release. |
| Unverified emulator/device test | Mark `NOT RUN`, never `PASS`. |

## 9. Definition of done

Builder MVP is ready for app integration only if: the chosen `APP_ID` is frozen; Bash plus its entire target dependency closure are built solely by our controlled pipeline; a clean local build and clean GitHub Actions build have artifact inventory and hashes; package contract validation passes; tests are correctly categorized as static/emulator/device; and the app can import one bootstrap artifact **without changing the format by hand**.

Until E1/E2 in [ARCHITECTURE.md](ARCHITECTURE.md) are proven on devices, builder outputs are **candidate packages**, not guaranteed runnable release packages.
