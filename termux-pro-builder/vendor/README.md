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
