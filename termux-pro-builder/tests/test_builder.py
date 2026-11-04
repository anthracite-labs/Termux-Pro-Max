import hashlib
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
