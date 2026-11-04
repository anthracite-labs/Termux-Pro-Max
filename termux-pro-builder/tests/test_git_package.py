import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
from test_builder import builder, ROOT


class GitPackage(unittest.TestCase):
    def test_android_curl_output_is_unversioned_and_missing_output_fails(self):
        recipe = json.loads((ROOT / 'recipes/curl.json').read_text())
        self.assertEqual(recipe['required_files'], ['lib/libcurl.so'])
        target = json.loads((ROOT.parent / 'shared/target.json').read_text())
        with zipfile.ZipFile(ROOT.parent / 'docs/evidence/oppo-cph2819-api36/proof-debug.apk') as apk:
            elf = apk.read('lib/arm64-v8a/libtp-launcher.so')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); stage = folder / 'stage'
            library = stage / target['prefix'].lstrip('/') / 'lib/libcurl.so'
            library.parent.mkdir(parents=True); library.write_bytes(elf)
            # Real NDK fixture bytes exercise the package carrier; this is not a curl runtime result.
            fixture = dict(recipe, dependencies=[], patches=[])
            source = {'version': '1.0', 'upstream': 'https://example.invalid/fixture', 'revision': 'v1',
                      'sha256': hashlib.sha256(elf).hexdigest(), 'license': 'MIT'}
            path = builder.package('fixture', source, fixture, stage, target, folder)
            _, payload = builder.contract.load_package(path, target)
            self.assertIn('lib/libcurl.so', payload); self.assertNotIn('lib/libcurl.so.4', payload)
            library.rename(library.with_name('libcurl.so.4'))
            with self.assertRaisesRegex(ValueError, 'missing required runtime files'):
                builder.package('fixture', source, fixture, stage, target, folder)

    def test_git_inventory_runtime_paths_and_dependency_failures(self):
        recipe = json.loads((ROOT / 'recipes/git.json').read_text())
        target = json.loads((ROOT.parent / 'shared/target.json').read_text()); prefix = target['prefix']
        manifest = {'id': 'git', 'commands': [{'name': name} for name in recipe['commands']]}
        payload = {'libexec/tp-real/' + name: name.encode() for name in recipe['commands']}
        payload['libexec/tp-real/git'] += (prefix + '/bin/bash').encode() + b'\0' + (prefix + '/bin').encode() + b'\0'
        payload['share/git-core/templates/info/exclude'] = b'template'
        curl = ('curl ' + prefix + '/etc/tls/cert.pem').encode() + b'\0'; ca = b'certificate fixture'
        dependencies = [({'id': name}, {}) for name in ['openssl', 'zlib', 'bash']]
        dependencies += [({'id': 'curl'}, {'lib/libcurl.so': curl}),
                         ({'id': 'ca-certificates', 'source': {'sha256': hashlib.sha256(ca).hexdigest()}}, {'etc/tls/cert.pem': ca})]
        def elf(data, executable=False):
            return {'runpath': [prefix + '/lib'], 'needed': ['libcurl.so'] if data == b'git-remote-http' else [],
                    'soname': 'libcurl.so' if data == curl else None}
        with mock.patch.object(builder.contract, 'inspect_elf', side_effect=elf):
            self.assertEqual(builder.verify_git_layout(manifest, payload, dependencies, target)['git_layout'], 'PASS_STATIC')
            for path in ['libexec/tp-real/git-remote-http', 'share/git-core/templates/info/exclude']:
                broken = dict(payload); del broken[path]
                with self.subTest(path=path), self.assertRaises(ValueError): builder.verify_git_layout(manifest, broken, dependencies, target)
            missing = [d for d in dependencies if d[0]['id'] != 'curl']
            with self.assertRaisesRegex(ValueError, 'closure incomplete'): builder.verify_git_layout(manifest, payload, missing, target)
            bad = copy.deepcopy(dependencies); bad[-1][1]['etc/tls/cert.pem'] = b'tampered'
            with self.assertRaisesRegex(ValueError, 'checksum'): builder.verify_git_layout(manifest, payload, bad, target)
            shell = dict(payload); shell['libexec/tp-real/git'] = b'wrong shell'
            with self.assertRaisesRegex(ValueError, 'runtime shell'): builder.verify_git_layout(manifest, shell, dependencies, target)
            wrong_exec = dict(payload); wrong_exec['libexec/tp-real/git'] = (prefix + '/bin/bash').encode() + b'\0/wrong/exec-path\0'
            with self.assertRaisesRegex(ValueError, 'exec-path'): builder.verify_git_layout(manifest, wrong_exec, dependencies, target)
            wrong_inventory = dict(manifest, commands=manifest['commands'][:-1])
            with self.assertRaisesRegex(ValueError, 'inventory'): builder.verify_git_layout(wrong_inventory, payload, dependencies, target)
        def wrong_needed(data, executable=False):
            result = elf(data, executable)
            if data == b'git-remote-http': result['needed'] = ['libcurl.so.4']
            return result
        with mock.patch.object(builder.contract, 'inspect_elf', side_effect=wrong_needed):
            with self.assertRaisesRegex(ValueError, 'HTTP helper'): builder.verify_git_layout(manifest, payload, dependencies, target)
        with mock.patch.object(builder.contract, 'inspect_elf', side_effect=lambda data, executable=False: dict(elf(data), soname='libcurl.so.4')):
            with self.assertRaisesRegex(ValueError, 'SONAME'): builder.verify_git_layout(manifest, payload, dependencies, target)
