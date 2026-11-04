# SonarQube remediation and source-verification review — 4 November 2026

Project: `anthracite-labs_Termux-Pro-Max`. Baseline: PR #6 head
`6f0eabc8fe787b15c8dbffef9da0c3c467d1a6a9`; remediation targets
`feature/gh-source-builder`, without merging either PR. All existing worktrees,
source caches, package outputs and device evidence are preserved.

## Findings and technical dispositions

| Issue key | Rule | Root cause / impact | Resolution and regression |
| --- | --- | --- | --- |
| `AaGlECFy3GVjRyY5uxFh` | `xml:S5332` | Terminal manifest leaves network policy implicit. API 30 minimum / target 36 already defaults to denying cleartext. | Explicit `usesCleartextTraffic="false"`; `test_both_applications_explicitly_reject_cleartext`. |
| `AaGlECHR3GVjRyY5uxFi` | `xml:S5332` | Proof manifest has the same implicit default. | Explicit denial; same regression. |
| `AaGlECHS3GVjRyY5uxFj` | `text:S8569` | Fixed direct dependency versions alone do not pin transitive artifacts or their bytes. | Lock plugin classpath and all project configurations; commit five lockfiles and SHA-256 verification metadata; `test_all_projects_lock_dependencies_and_verify_artifacts` and actual Gradle checksum-negative check. |
| `AaGlECHT3GVjRyY5uxFk` | `shell:S7688` | Terminal ABI guard uses `test` in a Bash script; current quoting already prevents splitting. | Bash `[[ ... ]]`, unchanged success/failure status; terminal orchestration positive and negative tests. |
| `AaGlECHT3GVjRyY5uxFl` | `shell:S7688` | Terminal SELinux guard has the same construct. | Same; includes empty, wildcard and permissive-policy rejection before installation. |
| `AaGlECHU3GVjRyY5uxFm` | `shell:S7688` | Proof ABI guard uses `test` in Bash. | Bash `[[ ... ]]`; fake-adb positive and fail-closed tests. |
| `AaGlECHU3GVjRyY5uxFn` | `shell:S7688` | Proof kernel guard uses `test` in Bash. | Same; wrong/empty kernel rejected with exit 1 and evidence collection. |
| `AaGlECHU3GVjRyY5uxFo` | `shell:S7688` | Proof SELinux guard uses `test` in Bash. | Same; empty/wildcard/permissive policy rejected. |
| `AaGlr_H7tGbFuSTC9lj5` | `python:S4790` | Git blob/tree object IDs require upstream's SHA-1 format. SHA-1 alone would be an unsafe source integrity check. | Retain interoperable object identity, explicitly `usedforsecurity=False`; independent mandatory SHA-256 and GPG checks remain. Security disposition below; source-substitution regression and independent native Git hash reference. |
| `AaGlr_H7tGbFuSTC9lj6` | `python:S4790` | Signed Git commit reconstruction requires the same SHA-1 object format. | Same disposition; pinned revision mismatch, payload/signature/keyring substitution, real expected-signer GPG and malformed-signature tests. |

The manifest setting applies to Android framework network clients which honor
that policy. It preserves normal system-trusted HTTPS and grants no permissions.
It is **not a firewall for native sockets**, including Git/curl/Go networking.
Their existing certificate and SSH host-key validation remain necessary.

Both acceptance runners declare `#!/usr/bin/env bash` and are invoked with Bash;
no POSIX-shell script was converted. False guards still exit 1 under `set -e`,
retain UNVERIFIED status and execute the EXIT log-collection trap.

## Git SHA-1 security review

Disposition: these two uses are required protocol/object identity operations,
not the cryptographic integrity authority for remotely obtained source bytes.
Changing them to SHA-256 would reject the pinned upstream SHA-1 Git repository
without improving the existing SHA-256 source pins. `usedforsecurity=False`
records that distinction for Python/OpenSSL; it does not strengthen SHA-1 or
disable any source check. No analyzer exclusion or `NOSONAR` suppression is used.

The reviewed trust chain for GH 2.103.3 is:

1. `fetch` requires HTTPS and checks the exact archive's pinned SHA-256 before
   any Git object reconstruction, even on cache hits:
   `1a64dc5be667fa8c6458c0e639292ee1a5e215854705db267882e1bcf865b335`.
2. Vendored signed payload and signature have separate mandatory SHA-256 pins:
   `579e0b04fd8388d58a9273eb6e9d8be10a7aa384584e726a3a2fe3908baab4f8`
   and `40b378eb207074197f88aa98fe86d4fa67c9f71706de4504dd26f6dc752e8b7d`.
3. Reconstructed commit identity must equal the immutable revision
   `63837fb778d6a39f02be0ce76ff89f2bc8d74bdc`, and archive Git tree must equal
   `bda6d94df1932516804907a320cb70e1524339b6` from the signed payload.
4. The keyring itself is SHA-256 pinned to
   `878730e9ece9143bb14d634d55aa56f0570876b00aa28cc310090fe7262f1122`.
   GPG must exit successfully and emit machine-readable VALIDSIG for exactly
   `968479A1AFF927E37D1A566BB5690EEEBB952194`; bad, expired and revoked
   signature statuses are rejected. Human-readable diagnostics cannot authorize
   a signer. Actual verification reports RSA/SHA-256 (OpenPGP digest ID 8).
5. Pinned SHA-256 checks of `go.mod`/`go.sum`, Go h1/SHA-256 module verification,
   source offers, payload SHA-256 manifests and package/ELF checks still apply.

A remote attacker substituting an archive with the same Git SHA-1 tree cannot
pass the independent exact-byte SHA-256 pin. A replaced signed payload,
signature or keyring fails its separate SHA-256 pin. Invalid signatures and
unexpected signers fail actual GPG verification. The regression explicitly
models a matching Git tree and proves a substituted carrier is rejected before
Git/GPG use; it does not claim to generate a SHA-1 collision.

Trust starts with the reviewed repository locks, not with an untrusted checksum
downloaded alongside source. A malicious change to trusted locks/verifier code
is outside this remote-substitution boundary and still requires code review.
Future source updates must independently review archive provenance, SHA-256
pins, signed revision and signer together. This implementation must never be
reused as a SHA-1-only verifier of arbitrary unpinned archives. SHA-1 collision
resistance is not asserted. General release security sign-off, including the
pre-existing upstream zlib DSA/SHA-1 limitation, remains open.

No separate issue-triage approval procedure exists in repository instructions;
this narrowly scoped review is performed under the remediation request. Sonar
false-positive disposition, if applied, refers only to the two Git identity
operations and does not accept SHA-1 as an integrity primitive.

## Gradle input controls and provenance

AGP 8.10.1, Gradle 8.11.1, JDK 21.0.9+10, Android SDK 36 and NDK
28.2.13676358 remain unchanged. Lockfiles cover the root plugin classpath and
all four Android modules, including instrumentation dependencies. Wrapper
distribution SHA-256 was already pinned. Verification metadata covers 377
artifact/metadata files using SHA-256, with metadata verification enabled and
no trusted-artifact bypass. Existing resolved versions were retained.

After generating candidate metadata, all 377 files (219,748,350 bytes) were
independently streamed again from official Google Maven or Maven Central HTTPS
repositories and compared with every SHA-256 pin: **377 matched, 0 mismatches**.
Each verification entry records its exact checked publisher URL. This is
TLS/publisher and reviewed-pin trust, not a claim of upstream PGP verification
or vulnerability-free dependencies. Gradle artifact signature verification is
not enabled; it is independent of mandatory target-source GPG verification.

Normal builds and CI use strict checksum verification, never
`--write-verification-metadata`, `--write-locks`, lenient or disabled verification.
For a deliberate dependency change, regenerate in a review branch, inspect the
resolved version changes, independently check new publisher bytes/checksums,
and review lockfiles and metadata together. Do not bless a verification failure
by blindly regenerating pins. Initial generation command:

```bash
./termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app \
  --write-locks --write-verification-metadata sha256 \
  :app:dependencies :proof:dependencies :terminal-view:dependencies \
  :terminal-emulator:dependencies :app:assembleDebug \
  :app:assembleDebugAndroidTest :app:lintDebug :proof:assembleDebug :proof:lintDebug
```

The isolated `ci/check-gradle-security.py` first resolves the locked production
plugin classpath with the committed checksums. It then corrupts only a temporary
copy of the AGP JAR checksum and requires Gradle to reject that exact artifact.
It leaves the production metadata, dependency cache and old worktrees untouched.

## Local verification and scope

Environment for Android commands:

```bash
export JAVA_HOME=/workspace/android-tools/jdk-21.0.9+10
export ANDROID_HOME=/workspace/android-tools/sdk
export GRADLE_USER_HOME=/workspace/android-tools/gradle-home
export TP_BOOTSTRAP_DIR=/workspace/checkpoint-builds/gh-final-20261104
```

Executed from the remediation worktree:

```bash
python3 -m unittest discover -s termux-pro-app/tests -v
python3 -m unittest discover -s shared/tests -v
python3 -m unittest discover -s termux-pro-builder/tests -v
python3 termux-pro-app/ci/check-gradle-security.py
./termux-pro-app/gradlew --offline --no-daemon -p termux-pro-app \
  --dependency-verification strict :app:assembleDebug \
  :app:assembleDebugAndroidTest :app:lintDebug :proof:assembleDebug :proof:lintDebug
for script in termux-pro-app/gradlew termux-pro-app/proof/build-native.sh \
  termux-pro-app/app/build-native.sh termux-pro-app/run-device-proof.sh \
  termux-pro-app/ci/*.sh termux-pro-builder/build.sh termux-pro-builder/recipes/*.sh; do
  bash -n "$script" || exit
done
for package in bash openssh git gh; do
  TP_OUTPUT_DIR=/workspace/checkpoint-builds/gh-final-20261104 \
    ./termux-pro-builder/build.sh test "$package" || exit
done
mkdir -p termux-pro-app/build/consumer-check
"$JAVA_HOME/bin/javac" -Xlint:all -d termux-pro-app/build/consumer-check \
  termux-pro-app/app/src/main/java/com/anthracitelabs/termuxpro/bootstrap/*.java \
  termux-pro-app/tests/BootstrapHost.java
"$JAVA_HOME/bin/java" -cp termux-pro-app/build/consumer-check \
  com.anthracitelabs.termuxpro.bootstrap.BootstrapHost closure \
  /workspace/checkpoint-builds/gh-final-20261104/packages shared/target.json
git diff --check
```

Results: 34 app/native/bootstrap/orchestration tests, 6 shared contract/evidence
tests and 17 builder/source-integrity/GH tests PASS (57 total). The real pinned
GH archive also passes `source_inputs` including exact SHA-256, revision/tree
and GPG verification. Production Python static package checks and Java consumer
PASS for the existing ten-package closure (GH records 160 source modules).
This locally revalidates preserved packages; it is not a new local source build.
The CI source-builder job performs a clean full build of the changed verifier.

Initial manifest/lock regressions failed as expected before remediation. An
early host run also encountered the sandbox's loopback-socket restriction and
a test assertion about Gradle's generated comment; the assertion was corrected
and the full suite passed with loopback execution enabled. Nothing was skipped.
Strict app, instrumentation and proof APK assembly and lint PASS. Lint reports
the existing warnings: app `SdCardPath` (2) / `DataExtractionRules` (1); proof
`UnsafeNativeCodeLocation`, `DataExtractionRules`, `MissingApplicationIcon`
and `SetTextI18n` (3); zero errors. Native launcher/proof builds ran through Gradle.
Logs are preserved under `/workspace/sonar-remediation-evidence/`.

## Sonar and Android acceptance status

Fresh initial Sonar results: main gate OK, eight OPEN listed issues; PR #6 gate
ERROR (new security rating 4/D), two OPEN Git SHA-1 issues. Both scopes have zero
security hotspots. No main issue is to be manually closed merely because a
change exists on an unmerged remediation branch. The new PR analysis/checks
and delivery report must distinguish branch fixes from main's unchanged scan.
The completed fresh PR #8 analysis of `d7c685855d5a65d662bea36e3c456df802d4c0ba`
reports gate **OK**, security/reliability/maintainability ratings **1/A**, zero
issues and zero security hotspots. Both original PR #6 SHA-1 issues were
individually reviewed with the threat model and immutable review link, changed
to `falsepositive`, and re-read as RESOLVED. PR #6's gate was recomputed as OK;
that disposition is not a new code scan of PR #6. The eight original main
issues remain OPEN until the fixes are merged and main is analyzed. No main
finding was manually hidden or accepted. Final-head analysis and CI conclusions
are recorded on [PR #8](https://github.com/anthracite-labs/Termux-Pro-Max/pull/8)
and its [Sonar dashboard](https://sonarcloud.io/dashboard?id=anthracite-labs_Termux-Pro-Max&pullRequest=8).

The first [CI run](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41815417933)
failed in a pre-existing Linux PTY test: a transient foreground process exited
between `/proc/<pid>/comm` existence and read calls. Dependent builds were
SKIPPED in that run. A deterministic injected process-disappearance regression
reproduced the failure. The test now retries a missing proc entry within its
original five-second deadline, still requires an actual foreground `sleep`,
then checks Ctrl+C status 130 and shell reaping. The full 34-test app suite
passes, including this regression. Production PTY/Android code is unchanged;
the final-head CI reruns all required jobs rather than treating skips as passes.

The next [CI run](https://github.com/anthracite-labs/Termux-Pro-Max/actions/runs/41815872709)
passed host tests but correctly failed strict Gradle verification for two missing
metadata entries: `guava-parent-33.3.1-jre.pom` and `junit-bom-5.10.2.module`.
The initial warm-cache generation had not recorded them. Both were independently
downloaded from Maven Central, SHA-256 checked and added, without changing any
resolved version or relaxing metadata verification. A focused regression now
requires these clean-resolution inputs. Fresh-cache local validation passed;
final-head CI is checked separately on PR #8. Original caches remain preserved.

With an initially empty dependency cache, strict local app, instrumentation and
proof APK builds and lint completed successfully in 2m 4s. Only the already
SHA-256-pinned Gradle distribution was reused; dependencies/metadata were fetched
again. The separate cache is preserved in the directory recorded by
`/workspace/sonar-remediation-evidence/fresh-gradle-home.txt`. Exact invocation:

```bash
fresh_gradle_home=$(mktemp -d /dev/shm/termux-sonar-gradle.XXXXXX)
ln -s /workspace/android-tools/gradle-home/wrapper "$fresh_gradle_home/wrapper"
GRADLE_USER_HOME="$fresh_gradle_home" ./termux-pro-app/gradlew --no-daemon \
  -p termux-pro-app -Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts \
  -Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 \
  -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080 --dependency-verification strict \
  :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug \
  :proof:assembleDebug :proof:lintDebug
```

`aapt2 dump xmltree <app-or-proof.apk> --file AndroidManifest.xml` also confirms
both compiled APK manifests retain `com.anthracitelabs.termuxpro`, min SDK 30,
target SDK 36 and `usesCleartextTraffic=false`. This is static APK inspection,
not Android network or application execution evidence.

Sonar dependency-risk analysis was attempted but Advanced Security is not
enabled for this organization; dependency vulnerability coverage was **not
performed**. Locks and checksums provide reproducibility/integrity, not SCA.

E0/E1 PASS applies only to the original OPPO CPH2819 Android 16 / API 36,
ARM64, 4 KB-page proof fixture recorded in VERIFICATION.md. No new device run
was performed. Android E2, terminal device acceptance and real E3 are **NOT RUN**.
Host tests, source builds, static validation, APK compilation, lint and Sonar
analysis cannot satisfy those Android runtime gates. No release is authorized.
