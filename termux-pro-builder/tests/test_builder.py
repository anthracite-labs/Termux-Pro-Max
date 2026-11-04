import hashlib
import importlib.util
import json
import io
from unittest import mock
import subprocess
import zipfile
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tp_builder', ROOT / 'builder.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class Builder(unittest.TestCase):
    def test_dependency_order_and_cycles(self):
        recipes = {'bash': {'dependencies': ['readline']},
                   'readline': {'dependencies': ['ncurses']}, 'ncurses': {'dependencies': []}}
        self.assertEqual(builder.plan('bash', recipes), ['ncurses', 'readline', 'bash'])
        combined = builder.plan('readline', recipes, done=builder.plan('bash', recipes))
        self.assertEqual(combined, ['ncurses', 'readline', 'bash'])
        recipes['ncurses']['dependencies'] = ['bash']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            builder.plan('bash', recipes)
        with self.assertRaisesRegex(ValueError, 'unknown'):
            builder.plan('missing', recipes)

    def test_bad_cached_source_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.tar.gz'
            path.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                builder.check_hash(path, hashlib.sha256(b'approved source').hexdigest())

    def test_source_offer_contains_verified_sources_and_build_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'cache'
            cache.mkdir()
            data = b'exact official source fixture'
            (cache / 'fixture.tar.gz').write_bytes(data)
            sources = {'fixture': {'url': 'https://example.org/fixture.tar.gz',
                                   'sha256': hashlib.sha256(data).hexdigest()}}
            output = Path(directory) / 'output'
            path = builder.source_offer(['fixture'], sources, cache, output)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read('upstream/fixture.tar.gz'), data)
                self.assertIn('build/termux-pro-builder/recipes/build-gnu.sh', archive.namelist())
                self.assertIn('build/termux-pro-builder/patches/bash/0001-android-paths.patch', archive.namelist())
                record = json.loads(archive.read('index.json'))
                for name, digest in record['files'].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                self.assertIn(b'NDK', archive.read('README.txt'))
            builder.check_hash(path, path.with_suffix('.sha256').read_text().split()[0])
            (cache / 'fixture.tar.gz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                builder.source_offer(['fixture'], sources, cache, output)

    def test_signature_identity_and_failed_statuses_cannot_be_overridden_by_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); cache = folder / 'cache'; cache.mkdir()
            archive = b'fixture source'; signature = b'fixture signature'
            (cache / 'source.tar.gz').write_bytes(archive)
            (cache / 'source.asc').write_bytes(signature)
            source = {'url': 'https://example.org/source.tar.gz',
                      'sha256': hashlib.sha256(archive).hexdigest(),
                      'signature_url': 'https://example.org/source.asc',
                      'signature_sha256': hashlib.sha256(signature).hexdigest(), 'signer': 'A' * 40}
            expected = '[GNUPG:] VALIDSIG ' + source['signer'] + ' remaining fields\n'
            with mock.patch.object(builder.subprocess, 'run') as run:
                run.return_value = subprocess.CompletedProcess([], 0, expected, 'display-only diagnostics')
                builder.source_inputs('fixture', source, cache, folder, io.StringIO())
                for stdout, stderr, code in [(expected, '', 1),
                                              (expected + '[GNUPG:] EXPKEYSIG bad key\n', '', 0),
                                              ('[GNUPG:] VALIDSIG ' + 'B' * 40 + ' fields\n', expected, 0)]:
                    run.return_value = subprocess.CompletedProcess([], code, stdout, stderr)
                    with self.assertRaises(ValueError):
                        builder.source_inputs('fixture', source, cache, folder, io.StringIO())

    def test_configure_fallback_cannot_publish_a_license_only_library_package(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); stage = folder / 'stage'
            target = {'prefix': '/data/user/0/com.anthracitelabs.termuxpro/files/usr'}
            license_file = stage / target['prefix'].lstrip('/') / 'share/licenses/fixture/LICENSE'
            license_file.parent.mkdir(parents=True); license_file.write_text('license fixture')
            recipe = {'commands': [], 'required_files': ['lib/libfixture.so']}
            with self.assertRaisesRegex(ValueError, 'missing required runtime files'):
                builder.package('fixture', {}, recipe, stage, target, folder)


if __name__ == '__main__':
    unittest.main()
