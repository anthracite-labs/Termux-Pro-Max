# Source-signature keys

`gnu-signers.gpg` contains only the two fingerprint-pinned source signers used by
sources.lock. Exported with GnuPG `--export-options export-minimal` from the GNU
keyring plus the updated ncurses maintainer self-certification. No private keys
or prebuilt target packages are present.

- GNU keyring: https://ftp.gnu.org/gnu/gnu-keyring.gpg
  Original downloaded SHA256: 8013de59880f7a59f53b6bd207f4d2a408d67b84a82fa9cba1dbbf443428e2db
- ncurses fingerprint: 19882D92DDA4C400C22C0D56CC2AF4472167BE03
  The aggregate GNU keyring had expired self-certification. Refreshed **that same
  fingerprint**, without trusting a replacement key, from
  https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x19882D92DDA4C400C22C0D56CC2AF4472167BE03
  Downloaded key SHA256: d3319cfd8f8c34bfe77268a078cd590ebdd350e75c7df465a31d6f05fe2023e5
- Bash/readline fingerprint: 7C0135FB088AAF6C66C650B9BB5869F064EA74AB

Source archive/signature digests and required signer fingerprints are independently
locked in sources.lock. GPG VALIDSIG must match, with expired/revoked/bad-signature
statuses rejected. A cryptographic signature/hash is not a source-code safety or
current vulnerability review. The key acquisition trust root is the listed TLS
sources and pinned fingerprints, not an asserted global GPG owner trust rating.

Termux Play recipe porting reference: commit
1d36a62274ef62cb123788b2b20956f75bbcb92b in termux-play-store/termux-packages.
Only the GNU cross-configuration conventions were reviewed; the backend below is
plain configure/make recipes, not the full upstream engine or binary repository.

## Core package source keys

`core-signers.gpg` is a minimal public-key export, SHA-256
`7f2bb3f346a3a15afc40871ef86974f9b2557cf1f258f8a03a40f351cd73f258`.
Each core source entry pins this keyring hash and its exact observed signing
fingerprint, in addition to source and detached-signature SHA-256 digests.

- zlib maintainer key: https://madler.net/madler/pgp.html (linked by zlib.net).
  Extracted ASCII key SHA-256: `27f818fd93326e4531c6b094f0edc4c331a1c77ec6449675a3929ae3274d85ac`.
  Fingerprint: `5ED46A6721D365587791E2AA783FCD8E58BCAFBA`.
  Upstream 1.3.2 uses DSA/SHA-1; default GPG verifies it without weak-algorithm
  override flags. The SHA-256 source lock is mandatory. This old signature
  algorithm is recorded as a release/security-review issue, not a strong modern
  authenticity guarantee.
- OpenSSL: https://openssl-library.org/source/pubkeys.asc, SHA-256
  `56e106cd1c44bdb117aec24795f6dfbecaa9bfa0a2901b85331f0059aad16d53`.
  Primary `B146647E45A7B33947AB226B2A2C87D161692D40`, observed signing subkey
  `C46ED3F2CBEFDA1FDAADA44264ED7B1DCCE71CB2`. The source archive hash also
  matches the official openssl/openssl release asset's SHA-256 metadata.
- OpenSSH: https://ftp.openbsd.org/pub/OpenBSD/OpenSSH/RELEASE_KEY.asc,
  linked by openssh.com/portable.html; SHA-256
  `c4a6f4692c9b8e75ec096add049fe0314b3ceff9410321f1e85907cf7a864269`.
  Fingerprint `7168B983815A5EEF59A4ADFD2A3F414E736060BA`.

Trust acquisition uses the listed official TLS sources and observed fingerprints.
It is not an independent maintainer identity audit. GPG machine status is parsed
separately from human diagnostics; a diagnostic line cannot satisfy signer checks.
