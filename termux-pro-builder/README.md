# Standalone source builder (candidate implementation)

Builds the Bash dependency closure (ncurses 6.5 → readline 8.2 → Bash 5.2.37)
from official GNU archives, pinned SHA-256 digests, detached signatures and
fingerprint-pinned public keys. Target packages are never obtained from Termux
or another binary repository. See `vendor/README.md` for key/porting provenance.

The backend is ordinary GNU configure/make. Recipes declare only dependencies,
exports and reviewed source patches. The engine plans/cycle-checks the complete
graph, compiles target libraries into a clean isolated sysroot, applies patches
with zero fuzz, stages runtime data/licenses, validates ELF/dependencies and
emits the shared v1 `.tpkg` format and bootstrap ZIP. Bash stays upstream Bash;
patches only bind Android paths and fix its wide-curses configure selection.

## Run

Requires Linux x86-64, Python 3.12+, make, gcc, patch, gpg, tic and pinned NDK r28c
28.2.13676358. Set ANDROID_HOME to an SDK containing that NDK, or TP_NDK_HOME to
the NDK itself. `shared/target.json` fixes app identity, ABI, API and prefix.

```sh
./build.sh doctor
./build.sh build bash
./build.sh test bash
./build.sh verify output/packages/bash-5.2.37.tpkg
./build.sh bootstrap
./build.sh source-offer # regenerate corresponding source without recompiling
```

`TP_SOURCE_CACHE` and `TP_OUTPUT_DIR` optionally select writable working storage;
`TP_JOBS` controls make parallelism. Default directories are cache/ and output/.
Source cache entries are rehashed before use and mismatches fail closed. Logs,
source signature status, doctor identity and static package reports live under
output/. Build outputs are candidates until corresponding Android tests pass.

`bootstrap.zip` contains the exact package archives and external hash index the
app consumes. The candidate app bundles those bytes; there is no automatic
runtime binary download. User HOME is not part of builder output.

`bootstrap` also emits `sources.zip` and its external checksum: exact verified
upstream archives/signatures plus tracked build scripts, patches, locks, keys and
contract. Publish this corresponding-source bundle alongside candidate binaries.
The Ubuntu `source-builder` Actions job runs the same entry point and publishes
`termux-pro-source-bootstrap` and `termux-pro-source-build-logs`. CI success must
be observed separately; configuring the job is not a passing build result.

A successful local build of all three packages and bootstrap has been performed;
this is not an Android load/PTY acceptance result or a byte-reproducibility claim.
The lock records the NDK/compiler identity and official NDK archive checksum.
A host container digest is still unresolved, so release/host-image acceptance is
not marked complete. Host tool versions are recorded, not silently declared pinned.

The `release` entry point fails explicitly while E2/E3, package/runtime, signing,
license/security, host-image and distribution gates remain unresolved. No bypass
flag or fabricated signing/provenance success is provided. Candidate zlib/OpenSSL/OpenSSH recipes are now present; see the checkpoint below.
Git/GH and Python/Node remain outstanding; unsupported names fail instead of
silently downloading prebuilt tools.

## Core-source checkpoint

`build.sh build openssh` plans zlib 1.3.2 and OpenSSL 3.5.9 before OpenSSH 10.6p1.
All three official source archives and detached signatures have been verified;
key acquisition, fingerprints and the upstream zlib signature limitation are in
vendor/README.md. zlib and OpenSSL now produce packages passing static checks.
Recipes require their actual shared libraries, so a configure fallback cannot
publish a package containing only documentation/licenses.

The OpenSSH client binaries ssh/ssh-keygen/ssh-keyscan compile and link after
narrow Bionic compatibility patches. Their ELF ABI/alignment/RUNPATH checks pass.
**OpenSSH packaging is not yet accepted:** source-location strings still contain
host workspace paths, which the package verifier rejects. The next change must
map source filenames during compilation, then run the complete clean CLI closure
and Java package-consumer checks. Do not weaken the host-path validator or call
this a passing Android SSH result. Client-only staging omits a daemon, privileged
helpers and host keys. HOME and DNS adaptations still require real Android tests.

Five builder unit tests pass, including required-runtime-output and signer/status
negative cases. Machine signature status is now separate from human diagnostics;
non-UTF-8 key display text cannot break decoding or satisfy the signer check.
`source-offer openssh` selects that source closure without compiling it.
