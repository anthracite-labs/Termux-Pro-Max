"""Source-carrier regression tests; real upstream signatures run in source-build CI."""
import copy
import hashlib
import io
import json
import lzma
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from test_builder import builder, ROOT


class SourceFormats(unittest.TestCase):
    def test_signature_covers_exact_uncompressed_bytes_and_temporary_file_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); cache = folder / 'cache'; cache.mkdir()
            plain = b'uncompressed signed source fixture'
            packed = lzma.compress(plain); signature = b'detached signature fixture'
            (cache / 'source.tar.xz').write_bytes(packed); (cache / 'source.tar.sign').write_bytes(signature)
            source = {'url': 'https://example.invalid/source.tar.xz', 'sha256': hashlib.sha256(packed).hexdigest(),
                      'signature_url': 'https://example.invalid/source.tar.sign',
                      'signature_sha256': hashlib.sha256(signature).hexdigest(),
                      'signature_format': 'uncompressed-tar', 'uncompressed_sha256': hashlib.sha256(plain).hexdigest()}
            verified = []
            def verify(name, path, sig, metadata, output, log):
                self.assertEqual(path.read_bytes(), plain); self.assertEqual(sig.read_bytes(), signature)
                verified.append(path)
            output = folder / 'output'
            with mock.patch.object(builder, 'verify_signature', side_effect=verify):
                self.assertEqual(builder.source_inputs('fixture', source, cache, output, io.StringIO()), cache / 'source.tar.xz')
            self.assertFalse(verified[0].exists())
            wrong = dict(source, uncompressed_sha256='0' * 64)
            with mock.patch.object(builder, 'verify_signature') as verify:
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    builder.source_inputs('fixture', wrong, cache, output, io.StringIO())
                verify.assert_not_called()
            with mock.patch.object(builder, 'verify_signature', side_effect=ValueError('bad signature')):
                with self.assertRaisesRegex(ValueError, 'bad signature'):
                    builder.source_inputs('fixture', source, cache, output, io.StringIO())
            self.assertFalse(list(output.glob('signature-*')))

    def test_single_file_input_preserves_source_bytes_and_requires_pinned_license(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); cache = folder / 'cache'; cache.mkdir()
            data = b'certificate source fixture\n'; (cache / 'cacert-fixture.pem').write_bytes(data)
            source = {'version': '1.0', 'upstream': 'https://example.invalid/fixture', 'revision': 'v1',
                      'url': 'https://example.invalid/cacert-fixture.pem', 'sha256': hashlib.sha256(data).hexdigest(),
                      'format': 'file', 'license': 'MPL-2.0'}
            recipe = json.loads((ROOT / 'recipes/ca-certificates.json').read_text())
            target = json.loads((ROOT.parent / 'shared/target.json').read_text())
            output = folder / 'output'
            with mock.patch.object(builder, 'doctor', return_value=(folder / 'unused-tool-bin', {})):
                builder.build('ca-certificates', {'ca-certificates': source}, {'ca-certificates': recipe}, {}, target, cache, output)
                manifest, payload = builder.contract.load_package(output / 'packages/ca-certificates-1.0.tpkg', target)
                self.assertEqual(payload['etc/tls/cert.pem'], data)
                self.assertEqual(manifest['source']['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(hashlib.sha256(payload['share/licenses/ca-certificates/LICENSE']).hexdigest(), recipe['license_file']['sha256'])
                bad = copy.deepcopy(recipe); bad['license_file']['sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    builder.build('ca-certificates', {'ca-certificates': source}, {'ca-certificates': bad}, {}, target, cache, folder / 'bad-output')
            self.assertEqual((cache / 'cacert-fixture.pem').read_bytes(), data)
