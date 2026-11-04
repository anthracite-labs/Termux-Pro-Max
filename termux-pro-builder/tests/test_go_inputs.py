import base64
import hashlib
import io
import json
import subprocess
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from unittest import mock
from test_builder import builder


class GoInputs(unittest.TestCase):
    def test_pinned_host_archive_version_and_cached_compiler_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            executable = b'#!/bin/sh\nprintf "go version go1.27.3 linux/amd64\\n"\n'
            archive = folder / 'go.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                entry = tarfile.TarInfo('go'); entry.type = tarfile.DIRTYPE; tar.addfile(entry)
                for name, data in [('bin/go', executable), ('src/runtime/runtime.go', b'compiler source')]:
                    entry = tarfile.TarInfo('go/' + name); entry.size = len(data); entry.mode = 0o755
                    tar.addfile(entry, io.BytesIO(data))
            lock = {'version': 'go1.27.3', 'url': 'https://example.invalid/go.tar.gz',
                    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                    'go_sha256': hashlib.sha256(executable).hexdigest()}
            root = builder.go_toolchain(lock, folder, folder / 'tools', io.StringIO())
            self.assertEqual((root / 'bin/go').read_bytes(), executable)
            (root / 'src/runtime/runtime.go').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Go toolchain'):
                builder.go_toolchain(lock, folder, folder / 'tools', io.StringIO())
            with self.assertRaisesRegex(ValueError, 'checksum'):
                builder.go_toolchain(dict(lock, sha256='0' * 64), folder, folder / 'other', io.StringIO())
            wrong = dict(lock, version='go1.27.2')
            with self.assertRaisesRegex(ValueError, 'Go version'):
                builder.go_toolchain(wrong, folder, folder / 'other', io.StringIO())

    def test_module_zip_and_mod_are_checked_against_pinned_go_sum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive = root / 'source.zip'; mod = root / 'source.mod'
            data = {'example.invalid/module@v1.0.0/LICENSE': b'MIT fixture',
                    'example.invalid/module@v1.0.0/main.go': b'package fixture\n'}
            with zipfile.ZipFile(archive, 'w') as zip:
                for path, content in data.items(): zip.writestr(path, content)
            mod.write_bytes(b'module example.invalid/module\n')
            def h1(files):
                summary = ''.join(hashlib.sha256(content).hexdigest() + '  ' + name + '\n' for name, content in sorted(files.items()))
                return 'h1:' + base64.b64encode(hashlib.sha256(summary.encode()).digest()).decode()
            checksum = h1(data); modsum = h1({'go.mod': mod.read_bytes()})
            sums = root / 'go.sum'
            sums.write_text('example.invalid/module v1.0.0 ' + checksum + '\nexample.invalid/module v1.0.0/go.mod ' + modsum + '\n')
            records = [{'Path': 'example.invalid/module', 'Version': 'v1.0.0', 'Zip': str(archive),
                        'GoMod': str(mod), 'Sum': checksum, 'GoModSum': modsum}]
            verified = builder.verify_go_modules(records, sums)
            self.assertEqual(verified[0]['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            mod.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'module checksum'):
                builder.verify_go_modules(records, sums)
            mod.write_bytes(b'module example.invalid/module\n')
            with zipfile.ZipFile(archive, 'a') as zip: zip.writestr('extra.go', b'tampered')
            with self.assertRaisesRegex(ValueError, 'module checksum'):
                builder.verify_go_modules(records, sums)
            sums.write_text('')
            with self.assertRaises(ValueError): builder.verify_go_modules(records, sums)

    def test_json_stream_errors_are_not_silently_discarded(self):
        self.assertEqual(list(builder.json_stream('{"a":1}\n{"b":2}')), [{'a': 1}, {'b': 2}])
        with self.assertRaises(ValueError): list(builder.json_stream('{"a":1}\ninvalid'))

    def test_source_archive_tree_matches_git_object_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.tar.gz'
            with tarfile.open(path, 'w:gz') as tar:
                entry = tarfile.TarInfo('source/hello.txt'); entry.size = 6
                tar.addfile(entry, io.BytesIO(b'hello\n'))
            blob = bytes.fromhex(subprocess.check_output(['git', 'hash-object', '--stdin'], input=b'hello\n').decode().strip())
            tree = b'100644 hello.txt\0' + blob
            expected = subprocess.check_output(['git', 'hash-object', '-t', 'tree', '--stdin'], input=tree).decode().strip()
            self.assertEqual(builder.archive_git_tree(path), expected)
            source = json.loads((builder.BASE / 'sources.lock').read_text())['gh']
            with mock.patch.object(builder, 'fetch', return_value=path):
                with self.assertRaisesRegex(ValueError, 'revision mismatch'):
                    builder.source_inputs('gh', dict(source, revision='0' * 40), Path(directory), Path(directory), io.StringIO())
                with self.assertRaisesRegex(ValueError, 'signed Git tree'):
                    builder.source_inputs('gh', source, Path(directory), Path(directory), io.StringIO())
            with tarfile.open(path, 'w:gz') as tar:
                entry = tarfile.TarInfo('../escape'); entry.size = 0; tar.addfile(entry, io.BytesIO(b''))
            with self.assertRaises(ValueError): builder.archive_git_tree(path)
