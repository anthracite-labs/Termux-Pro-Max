import hashlib
import importlib.util
import json
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


if __name__ == '__main__':
    unittest.main()
