import copy
import importlib.util
import json
from pathlib import Path
import struct
import hashlib
import tempfile
import stat
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'shared'))
import contract


class Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ROOT / 'docs/evidence/oppo-cph2819-api36/proof-debug.apk') as apk:
            cls.elf = apk.read('lib/arm64-v8a/libtp-launcher.so')
        cls.target = json.loads((ROOT / 'shared/target.json').read_text())

    def test_real_android_fixture_passes_static_elf_checks(self):
        result = contract.inspect_elf(self.elf, executable=True)
        self.assertIn('libc.so', result['needed'])

    def test_static_foreign_and_misaligned_elves_are_rejected(self):
        variants = []
        foreign = bytearray(self.elf)
        struct.pack_into('<H', foreign, 18, 62)
        variants.append(foreign)
        static = bytearray(self.elf)
        phoff = struct.unpack_from('<Q', static, 32)[0]
        count = struct.unpack_from('<H', static, 56)[0]
        misaligned = bytearray(self.elf)
        for i in range(count):
            offset = phoff + i * 56
            kind = struct.unpack_from('<I', static, offset)[0]
            if kind == 3:
                struct.pack_into('<I', static, offset, 0)
            if kind == 1:
                struct.pack_into('<Q', misaligned, offset + 48, 4096)
        variants.extend([static, misaligned, self.elf[:40]])
        for variant in variants:
            with self.subTest(size=len(variant)):
                with self.assertRaises(ValueError):
                    contract.inspect_elf(variant, executable=True)

    def test_paths_and_duplicate_json_are_rejected(self):
        for path in ['../home/x', '/etc/passwd', 'lib/../bin/x', 'lib//x', 'lib/./x', 'lib\\x', 'bin/gh']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                contract.payload_path(path)
        with self.assertRaises(ValueError):
            contract.read_json('{"schema":1,"schema":2}')

    def manifest(self):
        return {'schema': 1, 'id': 'fixture', 'version': '1.0', 'revision': 1,
                'abi': 'arm64-v8a', 'min_android_api': 30,
                'app_id': self.target['application_id'], 'prefix': self.target['prefix'],
                'source': {'upstream': 'https://example.invalid/fixture', 'revision': 'v1.0', 'sha256': '0' * 64},
                'dependencies': [], 'commands': [{'name': 'fixture', 'kind': 'elf', 'target': 'libexec/tp-real/fixture'}],
                'files': [{'path': 'libexec/tp-real/fixture', 'sha256': hashlib.sha256(self.elf).hexdigest(), 'mode': '0644'}],
                'licenses': ['MIT']}

    def write_package(self, path, manifest=None, data=None, extra=None):
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest or self.manifest()))
            entry = zipfile.ZipInfo('payload/libexec/tp-real/fixture')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, self.elf if data is None else data)
            if extra:
                archive.writestr(*extra)

    def test_package_checks_inventory_hash_identity_and_dependency_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tpkg'
            self.write_package(path)
            manifest, payload = contract.load_package(path, self.target)
            self.assertEqual(contract.verify_dependencies(manifest, payload, [])['status'], 'PASS_STATIC')
            manifest['dependencies'] = ['missing']
            with self.assertRaisesRegex(ValueError, 'dependency'):
                contract.verify_dependencies(manifest, payload, [])
            self.write_package(path, data=self.elf + b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                contract.load_package(path, self.target)
            for key, value in [('abi', 'x86_64'), ('app_id', 'com.termux'),
                               ('prefix', '/another/prefix'), ('schema', 2), ('schema', True)]:
                manifest = self.manifest(); manifest[key] = value
                self.write_package(path, manifest=manifest)
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    contract.load_package(path, self.target)

    def test_undeclared_traversal_and_zip_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tpkg'
            for extra in [('payload/../../home/key', b'bad'), ('payload/lib/extra', b'bad')]:
                self.write_package(path, extra=extra)
                with self.assertRaises(ValueError):
                    contract.load_package(path, self.target)
            link = zipfile.ZipInfo('payload/lib/link')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            self.write_package(path, extra=(link, b'../../home/key'))
            with self.assertRaisesRegex(ValueError, 'symlink'):
                contract.load_package(path, self.target)


if __name__ == '__main__':
    unittest.main()
