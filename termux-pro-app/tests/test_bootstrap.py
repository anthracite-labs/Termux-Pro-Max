"""Production Java consumer conformance and actual crash/recovery filesystem tests."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('shared_contract_test', ROOT / 'shared/tests/test_contract.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class Bootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.classes = Path(cls.folder.name) / 'classes'
        jdk = Path(os.environ.get('JAVA_HOME', '/usr')) / 'bin'
        cls.java = str(jdk / 'java')
        sources = list((ROOT / 'termux-pro-app/app/src/main/java/com/anthracitelabs/termuxpro/bootstrap').glob('*.java'))
        subprocess.run([str(jdk / 'javac'), '-Xlint:all', '-d', str(cls.classes), *map(str, sources),
                        str(ROOT / 'termux-pro-app/tests/BootstrapHost.java')], check=True)
        fixtures.Contract.setUpClass()
        cls.fixture = fixtures.Contract()
        cls.target_path = ROOT / 'shared/target.json'

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_java(self, command, path, *args, expected=0, target_path=None):
        result = subprocess.run([self.java, '-cp', str(self.classes),
                                 'com.anthracitelabs.termuxpro.bootstrap.BootstrapHost', command,
                                 str(path), str(target_path or self.target_path), *map(str, args)],
                                text=True, capture_output=True, timeout=20)
        if expected is None:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result


    def test_large_payload_verifies_under_android_sized_heap(self):
        # GH ships a large native payload. Validation must not expand it into
        # multiple full-size Java arrays/Strings on Android's 192 MiB heap.
        with tempfile.TemporaryDirectory() as directory:
            payload = bytearray(80 * 1024 * 1024)
            path = Path(directory) / 'large.tpkg'
            manifest = self.fixture.manifest()
            manifest['commands'] = []
            manifest['files'] = [{'path': 'share/large.bin', 'sha256': '', 'mode': '0644'}]

            def validate():
                manifest['files'][0]['sha256'] = hashlib.sha256(payload).hexdigest()
                with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                    archive.writestr('manifest.json', json.dumps(manifest))
                    entry = zipfile.ZipInfo('payload/share/large.bin')
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFREG | 0o644) << 16
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(entry, payload)
                return subprocess.run(
                    [self.java, '-Xmx192m', '-cp', str(self.classes),
                     'com.anthracitelabs.termuxpro.bootstrap.BootstrapHost',
                     'validate', str(path), str(self.target_path)],
                    capture_output=True, text=True, timeout=60)

            good = validate()
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)

            # Cross a 16 KiB read boundary; forbidden paths must still fail.
            forbidden = b'/workspace/'
            payload[16384 - 4:16384 - 4 + len(forbidden)] = forbidden
            bad = validate()
            self.assertNotEqual(bad.returncode, 0, bad.stdout)
            self.assertIn('foreign/host path', bad.stderr)

    def test_same_native_contract_fixture_and_negative_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.tpkg'
            self.fixture.write_package(path)
            self.run_java('validate', path)
            cases = [('abi', 'x86_64'), ('prefix', '/wrong'), ('schema', True),
                     ('app_id', 'com.termux'), ('dependencies', ['missing'])]
            for field, value in cases:
                manifest = self.fixture.manifest(); manifest[field] = value
                self.fixture.write_package(path, manifest=manifest)
                with self.subTest(field=field): self.run_java('validate', path, expected=None)
            variants = []
            foreign = bytearray(self.fixture.elf); struct.pack_into('<H', foreign, 18, 62); variants.append(foreign)
            static = bytearray(self.fixture.elf)
            phoff = struct.unpack_from('<Q', static, 32)[0]
            count = struct.unpack_from('<H', static, 56)[0]
            misaligned = bytearray(self.fixture.elf)
            for i in range(count):
                at = phoff + i * 56
                kind = struct.unpack_from('<I', static, at)[0]
                if kind == 3: struct.pack_into('<I', static, at, 0)
                if kind == 1: struct.pack_into('<Q', misaligned, at + 48, 4096)
            variants.extend([static, misaligned, self.fixture.elf[:40]])
            for data in variants:
                manifest = self.fixture.manifest()
                manifest['files'][0]['sha256'] = hashlib.sha256(data).hexdigest()
                self.fixture.write_package(path, manifest=manifest, data=data)
                self.run_java('validate', path, expected=None)
                with self.assertRaises(ValueError): fixtures.contract.load_package(path, self.fixture.target)
            self.fixture.write_package(path, data=self.fixture.elf + b'tampered')
            self.run_java('validate', path, expected=None)
            link = zipfile.ZipInfo('payload/lib/link'); link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            for extra in [('payload/../../home/key', b'escape'), ('payload/lib/unlisted', b'bad'), (link, b'../../home/key')]:
                self.fixture.write_package(path, extra=extra)
                self.run_java('validate', path, expected=None)
            self.fixture.write_package(path)
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('manifest.json', '{}')
            self.run_java('validate', path, expected=None)

    def bootstrap(self, directory, root, version):
        manifest = self.fixture.manifest(); manifest['prefix'] = str(root / 'usr')
        manifest['version'] = version
        package = directory / f'fixture-{version}.tpkg'
        self.fixture.write_package(package, manifest=manifest)
        index = {'schema': 1, 'app_id': manifest['app_id'], 'prefix': manifest['prefix'],
                 'abi': manifest['abi'], 'min_android_api': manifest['min_android_api'],
                 'packages': [{'id': 'fixture', 'path': 'packages/' + package.name,
                               'sha256': hashlib.sha256(package.read_bytes()).hexdigest()}]}
        path = directory / f'bootstrap-{version}.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('index.json', json.dumps(index))
            archive.write(package, 'packages/' + package.name)
        return path

    def test_crash_at_each_transaction_boundary_preserves_home_and_complete_prefix(self):
        for point in ['staged', 'prepared', 'old-moved', 'new-moved', 'committed']:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory); root = folder / 'files'; root.mkdir()
                home = root / 'home'; home.mkdir(); (home / 'important').write_text('preserve me')
                launcher = folder / 'protected-launcher'; launcher.write_text('fixture'); launcher.chmod(0o700)
                old = self.bootstrap(folder, root, '1.0'); new = self.bootstrap(folder, root, '2.0')
                self.run_java('install', old, root, launcher)
                self.run_java('install', new, root, launcher, point, expected=77)
                self.run_java('recover', root)
                installed = json.loads((root / 'usr/var/lib/termux-pro/packages/fixture.json').read_text())
                self.assertEqual(installed['version'], '2.0' if point == 'committed' else '1.0')
                self.assertEqual((home / 'important').read_text(), 'preserve me')
                self.assertFalse((root / '.tp-stage').exists())
                self.assertFalse((root / '.tp-backup').exists())
                self.assertFalse((root / 'tp-install.journal').exists())

    def test_reuse_repairs_launcher_after_apk_update_without_replacing_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); root = folder / 'files'; root.mkdir()
            one = folder / 'launcher-one'; one.write_text('one'); one.chmod(0o700)
            two = folder / 'launcher-two'; two.write_text('two'); two.chmod(0o700)
            bootstrap = self.bootstrap(folder, root, '1.0')
            self.run_java('install', bootstrap, root, one)
            sentinel = root / 'usr/tmp/session-data'; sentinel.write_text('keep runtime')
            self.run_java('install', bootstrap, root, two)
            self.assertEqual((root / 'usr/bin/fixture').readlink(), two)
            self.assertEqual(sentinel.read_text(), 'keep runtime')
            (root / 'usr/libexec/tp-real/fixture').write_bytes(b'corruption')
            self.run_java('install', bootstrap, root, two, expected=None)
            self.assertEqual(sentinel.read_text(), 'keep runtime')

    def test_private_directory_alias_keeps_the_frozen_literal_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); real = folder / 'real-files'; real.mkdir()
            alias = folder / 'alias-files'; alias.symlink_to(real, target_is_directory=True)
            launcher = folder / 'launcher'; launcher.write_text('fixture'); launcher.chmod(0o700)
            bootstrap = self.bootstrap(folder, alias, '1.0')
            self.run_java('install', bootstrap, alias, launcher)
            installed = json.loads((real / 'usr/var/lib/termux-pro/packages/fixture.json').read_text())
            self.assertEqual(installed['prefix'], str(alias / 'usr'))
            self.assertEqual((real / 'usr/bin/fixture').readlink(), launcher)

    def test_alias_handling_rejects_other_private_roots_and_symlinked_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); real = folder / 'files'; real.mkdir()
            other = folder / 'other-profile'; other.mkdir()
            home = real / 'home'; home.mkdir(); (home / 'keep').write_text('private data')
            launcher = folder / 'launcher'; launcher.write_text('fixture'); launcher.chmod(0o700)
            bootstrap = self.bootstrap(folder, real, '1.0')
            target = dict(self.fixture.target); target['prefix'] = str(real / 'usr')
            target_file = folder / 'target.json'; target_file.write_text(json.dumps(target))
            self.run_java('install-bound', bootstrap, other, launcher, target_path=target_file, expected=None)
            (real / 'usr').symlink_to(other, target_is_directory=True)
            self.run_java('install-bound', bootstrap, real, launcher, target_path=target_file, expected=None)
            self.assertEqual((home / 'keep').read_text(), 'private data')
            self.assertFalse((other / 'bin').exists())

    def test_duplicate_json_keys_and_trailing_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'json'
            for text in ['{"a":1,"a":2}', '{"schema":1} true', '{"x":NaN}', '{"x":01}', '[1,]']:
                path.write_text(text)
                self.run_java('json', path, expected=None)
