"""SHA-256 pins and real GPG authentication are independent of Git object IDs."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from test_builder import builder


class SignedSourceSecurity(unittest.TestCase):
    def setUp(self):
        self.source = json.loads((builder.BASE / 'sources.lock').read_text())['gh']

    def test_archive_substitution_is_rejected_even_if_git_tree_would_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / self.source['url'].rsplit('/', 1)[1]).write_bytes(b'substituted source')
            with mock.patch.object(builder, 'archive_git_tree') as tree, mock.patch.object(builder, 'verify_signature') as verify:
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    builder.source_inputs('gh', self.source, root, root, io.StringIO())
                tree.assert_not_called()
                verify.assert_not_called()

    def test_payload_signature_and_keyring_substitution_cannot_reach_gpg(self):
        for field in ['payload', 'signature', 'keyring']:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = copy.deepcopy(self.source)
                for relative in [source['signed_commit']['payload'], source['signed_commit']['signature'], source['keyring']]:
                    dest = root / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(builder.BASE / relative, dest)
                archive = root / source['url'].rsplit('/', 1)[1]
                archive.write_bytes(b'fixture carrier')
                source['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
                relative = source['keyring'] if field == 'keyring' else source['signed_commit'][field]
                (root / relative).write_bytes(b'substituted ' + field.encode())
                payload = root / source['signed_commit']['payload']
                tree = payload.read_bytes().splitlines()[0][5:].decode() if field != 'payload' else ''
                with mock.patch.object(builder, 'BASE', root), mock.patch.object(builder, 'archive_git_tree', return_value=tree), mock.patch.object(builder.subprocess, 'run') as gpg:
                    with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                        builder.source_inputs('gh', source, root, root, io.StringIO())
                    gpg.assert_not_called()

    def test_real_pinned_signature_and_wrong_signer_or_malformed_signature(self):
        payload = builder.BASE / self.source['signed_commit']['payload']
        signature = builder.BASE / self.source['signed_commit']['signature']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder.verify_signature('gh', payload, signature, self.source, root, io.StringIO())
            with self.assertRaisesRegex(ValueError, 'signature verification failed'):
                builder.verify_signature('gh', payload, signature, dict(self.source, signer='0' * 40), root, io.StringIO())
            malformed = root / 'malformed.asc'
            malformed.write_bytes(b'not an OpenPGP signature')
            with self.assertRaisesRegex(ValueError, 'signature verification failed'):
                builder.verify_signature('gh', payload, malformed, self.source, root, io.StringIO())
