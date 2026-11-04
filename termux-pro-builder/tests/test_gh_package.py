import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from test_builder import builder


class GhPackage(unittest.TestCase):
    def test_layout_provenance_closure_and_negative_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prefix = '/data/user/0/com.anthracitelabs.termuxpro/files/usr'
            binary = b'policy fixture: ' + (prefix + '/bin/gh').encode()
            mod, sums = b'module example.invalid/fixture\n', b'example.invalid/dep v1 h1:fixture\nexample.invalid/dep v1/go.mod h1:mod\n'
            source = {'version': '1', 'revision': 'a' * 40, 'sha256': 'b' * 64,
                      'go_mod_sha256': hashlib.sha256(mod).hexdigest(), 'go_sum_sha256': hashlib.sha256(sums).hexdigest()}
            toolchain = {'version': 'go1.27.3', 'sha256': 'c' * 64}
            (base / 'sources.lock').write_text(json.dumps({'gh': source}))
            (base / 'toolchain.lock').write_text(json.dumps({'go': toolchain}))
            module = {'path': 'example.invalid/dep', 'version': 'v1', 'sum': 'h1:fixture', 'go_mod_sum': 'h1:mod',
                      'licenses': ['share/licenses/gh/modules/dep/LICENSE']}
            info = {'GoVersion': 'go1.27.3', 'Path': 'github.com/cli/cli/v2/cmd/gh',
                    'Deps': [{'Path': module['path'], 'Version': 'v1', 'Sum': module['sum']}],
                    'Settings': [{'Key': k, 'Value': v} for k, v in {'GOOS': 'android', 'GOARCH': 'arm64', 'CGO_ENABLED': '1', '-buildmode': 'pie', '-trimpath': 'true'}.items()]}
            record = {'toolchain': toolchain, 'source_revision': source['revision'], 'source_sha256': source['sha256'],
                      'binary_sha256': hashlib.sha256(binary).hexdigest(), 'go_info': info, 'modules': [module]}
            manifest = {'id': 'gh', 'version': '1', 'source': source,
                        'commands': [{'name': 'gh', 'kind': 'elf', 'target': 'libexec/tp-real/gh'}]}
            payload = {'libexec/tp-real/gh': binary, 'share/gh/go.mod': mod, 'share/gh/go.sum': sums,
                       'share/licenses/gh/LICENSE': b'MIT', 'share/licenses/gh/Go-LICENSE': b'BSD',
                       module['licenses'][0]: b'license', 'share/gh/build-inputs.json': json.dumps(record).encode()}
            deps = [({'id': name}, {}) for name in ['git', 'openssh', 'ca-certificates', 'bash']]
            # Policy-only fixture; real ARM64 Go ELF is checked by clean source-build integration.
            elf = {'runpath': [prefix + '/lib'], 'needed': ['libc.so']}
            with mock.patch.object(builder, 'BASE', base):
                with mock.patch.object(builder.contract, 'inspect_elf', return_value=elf):
                    self.assertEqual(builder.verify_gh_layout(manifest, payload, deps, {'prefix': prefix})['go_modules'], 1)
                    for broken in [dict(manifest, commands=[]), dict(manifest, version='wrong')]:
                        with self.assertRaises(ValueError): builder.verify_gh_layout(broken, payload, deps, {'prefix': prefix})
                    with self.assertRaisesRegex(ValueError, 'closure'):
                        builder.verify_gh_layout(manifest, payload, deps[1:], {'prefix': prefix})
                    for field in ['toolchain', 'source_sha256', 'binary_sha256', 'go_info', 'modules']:
                        bad = copy.deepcopy(record)
                        if field == 'toolchain': bad[field]['version'] = 'wrong'
                        elif field == 'go_info': bad[field]['Settings'][0]['Value'] = 'linux'
                        elif field == 'modules': bad[field][0]['sum'] = 'wrong'
                        else: bad[field] = 'wrong'
                        broken = dict(payload, **{'share/gh/build-inputs.json': json.dumps(bad).encode()})
                        with self.subTest(field=field), self.assertRaises(ValueError):
                            builder.verify_gh_layout(manifest, broken, deps, {'prefix': prefix})
                    broken = dict(payload); del broken[module['licenses'][0]]
                    with self.assertRaisesRegex(ValueError, 'license'):
                        builder.verify_gh_layout(manifest, broken, deps, {'prefix': prefix})
                # A malformed/native-incompatible binary cannot bypass the production ELF check.
                with self.assertRaisesRegex(ValueError, 'ELF'):
                    builder.verify_gh_layout(manifest, payload, deps, {'prefix': prefix})
