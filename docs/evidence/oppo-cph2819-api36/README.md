# OPPO CPH2819 E0/E1 fixture evidence

E0 and E1 **PASS for this one device and fixture**: OPPO CPH2819, Android 16 /
API 36, targetSdk 36, arm64-v8a, 4096-byte pages. All eight expected case exits
match; all argv0 diagnostics decode to `forged-git`. E2/E3 are NOT RUN.

The APK SHA-256 is `7c9c136ffc7d974b54330aedfae200cb47a096cc6b8d1934cbc4b8aba8455bc3`.
Its v2 APK signature verifies. Its native executable hashes match the NDK-built
fixtures. `source-revision.txt` in the supplied archive identifies
[`c54afee`](https://github.com/anthracite-labs/Termux-Pro-Max/commit/c54afeecf57b5863088ae9586f01c85a3f9232ee),
a GitHub PR merge of `d70e8d3` into `df162f0`; the proof source tree is identical
to `d70e8d3`. This is not attribution to whichever branch HEAD exists later.

`record.json` records the observed checks, limitations and artifact identities.
`device-proof.redacted.log` is the supplied public log. `proof-debug.apk` preserves
the tested APK bytes. Verify their hashes with `sha256sum -c SHA256SUMS`.

The entire supplied evidence ZIP was inspected and all its manifest checksums
verified. The full raw log remains in the original attachment and local scratch
copy; its SHA-256 is `8d6a660195e9957d6c3e43907d5704c764be31de81c750a063f48e5a4dcc36c0`.
No raw fingerprint/install paths are published here. The original earlier upload
ZIP is absent, so its asserted hash cannot be independently checked here.

Provenance: user-supplied device output, not an agent-attached device session.
There is no in-log timestamp, signature or cryptographic binding of the log to
the APK. The user's device report is accepted with that limitation. This does
not prove a production ownership registry, universal invocation interception,
16 KB devices, other APIs/OEMs, explicit linker target loading or GH/Git/SSH.
