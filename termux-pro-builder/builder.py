#!/usr/bin/env python3
"""Source-only Android package builds; no target package repository or plugin DSL."""
import hashlib
import base64
import json
import gzip
import lzma
import tempfile
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
sys.path.insert(0, str(ROOT / 'shared'))
import contract


def check_hash(path, expected):
    with open(path, 'rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    contract.require(actual == expected, f'checksum mismatch: {path.name}: expected {expected}, got {actual}')
    return actual


def plan(name, recipes, active=None, done=None):
    active, done = list(active or []), list(done or [])
    contract.require(name in recipes, f'unknown package: {name}')
    contract.require(name not in active, f'dependency cycle: {" -> ".join(active + [name])}')
    if name in done:
        return done
    for dep in recipes[name]['dependencies']:
        done = plan(dep, recipes, active + [name], done)
    return done + [name]


def fetch(url, path, digest):
    contract.require(url.startswith('https://'), 'source must use HTTPS')
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        partial = path.with_suffix(path.suffix + '.partial')
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=90) as source, open(partial, 'wb') as output:
                    shutil.copyfileobj(source, output)
                try:
                    check_hash(partial, digest)
                except ValueError:
                    if attempt == 2:
                        raise
                    continue
                partial.replace(path)
                break
            finally:
                partial.unlink(missing_ok=True)
    check_hash(path, digest)
    return path


def json_stream(data):
    decoder = json.JSONDecoder()
    while data.strip():
        data = data.lstrip()
        value, end = decoder.raw_decode(data)
        yield value
        data = data[end:]


def go_toolchain(lock, cache, installation, log):
    archive = fetch(lock['url'], cache / lock['url'].rsplit('/', 1)[1], lock['sha256'])
    root = Path(os.environ.get('TP_GO_HOME', installation / lock['version'] / 'go'))
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        contract.require(all(m.name == PurePosixPath(m.name).as_posix() and '..' not in PurePosixPath(m.name).parts
                             and ((m.name == 'go' and m.isdir()) or (m.name.startswith('go/') and (m.isfile() or m.isdir())))
                             for m in members), 'unsupported Go toolchain archive')
        if not root.exists():
            contract.require('TP_GO_HOME' not in os.environ, 'configured Go toolchain is missing')
            root.parent.mkdir(parents=True, exist_ok=True)
            tar.extractall(root.parent, filter='data')
        contract.require(not root.is_symlink() and not any(p.is_symlink() for p in root.rglob('*')), 'symlinked Go toolchain')
        expected = set()
        for member in members:
            if member.isfile():
                path = root.parent / member.name
                expected.add(path.relative_to(root).as_posix())
                contract.require(path.is_file() and not path.is_symlink()
                                 and hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(tar.extractfile(member).read()).digest(),
                                 'cached Go toolchain differs from verified archive: ' + member.name)
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if not p.is_dir()}
        contract.require(actual == expected, 'unexpected Go toolchain files')
    check_hash(root / 'bin/go', lock['go_sha256'])
    env = dict(os.environ, GOTOOLCHAIN='local', GOENV='off', GOROOT=str(root))
    version = subprocess.check_output([str(root / 'bin/go'), 'version'], env=env, text=True).strip()
    contract.require(version == 'go version ' + lock['version'] + ' linux/amd64', 'Go version/host mismatch')
    log.write(version + '; official host archive SHA256=' + lock['sha256'] + '\n'); log.flush()
    return root


def go_h1(files):
    summary = hashlib.sha256()
    for name, data in sorted(files):
        contract.require('\n' not in name, 'invalid Go module filename')
        summary.update((hashlib.sha256(data).hexdigest() + '  ' + name + '\n').encode())
    return 'h1:' + base64.b64encode(summary.digest()).decode()


def verify_go_modules(records, sums):
    pinned = {}
    for line in sums.read_text().splitlines():
        name, version, digest = line.split()
        contract.require((name, version) not in pinned, 'duplicate Go checksum pin')
        pinned[name, version] = digest
    verified, seen = [], set()
    for record in records:
        key = record['Path'], record['Version']
        contract.require(not record.get('Error') and not record.get('Replace') and key not in seen, 'unsupported Go module record')
        seen.add(key)
        with zipfile.ZipFile(record['Zip']) as archive:
            names = archive.namelist()
            contract.require(len(names) == len(set(names)), 'duplicate Go module ZIP member')
            digest = go_h1((name, archive.read(name)) for name in names)
        mod = Path(record['GoMod']).read_bytes()
        mod_digest = go_h1([('go.mod', mod)])
        contract.require(pinned.get(key) == record['Sum'] == digest
                         and pinned.get((key[0], key[1] + '/go.mod')) == record['GoModSum'] == mod_digest,
                         'Go module checksum does not match pinned go.sum: ' + key[0])
        verified.append({'path': key[0], 'version': key[1], 'sum': digest, 'go_mod_sum': mod_digest,
                         'sha256': hashlib.sha256(Path(record['Zip']).read_bytes()).hexdigest(),
                         'go_mod_sha256': hashlib.sha256(mod).hexdigest()})
    contract.require(verified, 'empty Go module closure')
    return verified


def doctor(lock, target, output):
    contract.require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'build host must be Linux x86-64')
    for tool in ['make', 'patch', 'gcc', 'gpg', 'tic', 'perl']:
        contract.require(shutil.which(tool), f'missing host tool: {tool}')
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT', '')
    ndk = Path(os.environ.get('TP_NDK_HOME', str(Path(sdk) / 'ndk' / lock['ndk_revision']))).resolve()
    properties = ndk / 'source.properties'
    contract.require(properties.exists() and f'Pkg.Revision = {lock["ndk_revision"]}' in properties.read_text(), 'NDK revision mismatch; set TP_NDK_HOME or ANDROID_HOME')
    binaries = ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin'
    check_hash(binaries / 'clang', lock['clang_sha256'])
    check_hash(BASE / 'vendor/gnu-signers.gpg', lock['signer_keyring_sha256'])
    output.mkdir(parents=True, exist_ok=True)
    contract.require(shutil.disk_usage(output).free > 256 * 1024 * 1024, 'insufficient build disk space')
    record = {'status': 'PASS_TOOL_CHECKS', 'target': target, 'ndk': lock['ndk_revision'],
              'clang': subprocess.check_output([str(binaries / 'clang'), '--version'], text=True).splitlines()[0],
              'host_os': platform.platform(), 'python': platform.python_version(),
              'host_image_digest': lock['host_image_digest'],
              'release_ready': False, 'note': 'Device gates and host-image/security review remain required.'}
    (output / 'doctor.json').write_text(json.dumps(record, indent=2) + '\n')
    return binaries, record


def verify_signature(name, archive, signature, source, output, log):
    home = output / 'gpg-home'
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    keyring = BASE / source.get('keyring', 'vendor/gnu-signers.gpg')
    if 'keyring_sha256' in source:
        check_hash(keyring, source['keyring_sha256'])
    command = ['gpg', '--no-options', '--homedir', str(home), '--batch', '--no-default-keyring',
               '--keyring', str(keyring), '--status-fd', '1', '--verify', str(signature), str(archive)]
    result = subprocess.run(command, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.write(result.stdout + result.stderr); log.flush()
    statuses = result.stdout.splitlines()
    contract.require(result.returncode == 0 and any(line.startswith('[GNUPG:] VALIDSIG ' + source['signer'] + ' ') for line in statuses), f'source signature verification failed: {name}')
    contract.require(not any(any(f'[GNUPG:] {tag} ' in line for tag in ['EXPKEYSIG', 'REVKEYSIG', 'BADSIG', 'ERRSIG', 'EXPSIG']) for line in statuses), f'unacceptable source signature: {name}')


def archive_git_tree(archive):
    def object_hash(kind, data):
        # Git SHA-1 object identity only; source integrity uses pinned SHA-256
        # and GPG authentication in source_inputs. See docs/SONAR_REMEDIATION.md.
        return hashlib.sha1(kind + b' ' + str(len(data)).encode() + b'\0' + data, usedforsecurity=False).digest()
    root, archive_root = {}, None
    with tarfile.open(archive) as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            contract.require(not path.is_absolute() and '..' not in path.parts, 'unsafe signed source path')
            archive_root = archive_root or path.parts[0]
            contract.require(path.parts[0] == archive_root, 'signed source requires one root')
            if member.isdir():
                continue
            contract.require(len(path.parts) > 1 and (member.isfile() or member.issym()), 'unsupported signed source member')
            node = root
            for part in path.parts[1:-1]:
                node = node.setdefault(part, {})
                contract.require(isinstance(node, dict), 'signed source path collision')
            contract.require(path.name not in node, 'duplicate signed source path')
            mode = b'120000' if member.issym() else (b'100755' if member.mode & 0o111 else b'100644')
            data = member.linkname.encode() if member.issym() else tar.extractfile(member).read()
            node[path.name] = mode, object_hash(b'blob', data)
    def tree(node):
        data = b''
        for name, item in sorted(node.items(), key=lambda pair: (pair[0] + ('/' if isinstance(pair[1], dict) else '')).encode()):
            mode, digest = (b'40000', tree(item)) if isinstance(item, dict) else item
            data += mode + b' ' + name.encode() + b'\0' + digest
        return object_hash(b'tree', data)
    return tree(root).hex()


def source_inputs(name, source, cache, output, log):
    archive = fetch(source['url'], cache / source['url'].rsplit('/', 1)[1], source['sha256'])
    if source.get('signed_commit'):
        signed = source['signed_commit']
        payload, signature = BASE / signed['payload'], BASE / signed['signature']
        check_hash(payload, signed['payload_sha256']); check_hash(signature, signed['signature_sha256'])
        header, message = payload.read_bytes().split(b'\n\n', 1)
        raw = header + b'\ngpgsig ' + signature.read_bytes().replace(b'\n', b'\n ') + b'\n\n' + message
        # Reconstruct upstream's Git object ID; never use it as the integrity pin.
        commit = hashlib.sha1(b'commit ' + str(len(raw)).encode() + b'\0' + raw, usedforsecurity=False).hexdigest()
        contract.require(commit == source['revision'], 'signed commit revision mismatch')
        contract.require(header.splitlines()[0] == ('tree ' + archive_git_tree(archive)).encode(), 'source archive differs from signed Git tree')
        verify_signature(name, payload, signature, source, output, log)
    if source.get('signature_url'):
        signature = fetch(source['signature_url'], cache / source['signature_url'].rsplit('/', 1)[1], source['signature_sha256'])
        format = source.get('signature_format', 'archive')
        contract.require(format in {'archive', 'uncompressed-tar'}, 'unsupported source signature format')
        if format == 'uncompressed-tar':
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='signature-', dir=output) as directory:
                plain = Path(directory) / 'source.tar'
                opener = {'.xz': lzma.open, '.gz': gzip.open}.get(archive.suffix)
                contract.require(opener is not None, 'unsupported signed source compression')
                with opener(archive, 'rb') as input, open(plain, 'wb') as dest:
                    total = 0
                    while chunk := input.read(1024 * 1024):
                        total += len(chunk)
                        contract.require(total <= 512 * 1024 * 1024, 'signed source decompression limit')
                        dest.write(chunk)
                check_hash(plain, source['uncompressed_sha256'])
                verify_signature(name, plain, signature, source, output, log)
        else:
            verify_signature(name, archive, signature, source, output, log)
    return archive


def zip_bytes(archive, name, data, mode=0o644):
    entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_identity():
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)
    digest = hashlib.sha256()
    inputs = [ROOT / 'shared/target.json', ROOT / 'shared/contract.py']
    inputs += [p for p in BASE.rglob('*') if p.is_file() and p.suffix in {'.py', '.sh', '.json', '.patch', '.gpg', '.lock'}
               and not any(part in {'output', 'cache', '__pycache__'} for part in p.relative_to(BASE).parts)]
    for path in sorted(inputs):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return revision + ('+dirty' if dirty else ''), digest.hexdigest()


def package(name, source, recipe, stage, target, output):
    prefix = stage / target['prefix'].lstrip('/')
    payload = {}
    for root_name in ['lib', 'libexec', 'share', 'etc']:
        folder = prefix / root_name
        if not folder.exists():
            continue
        for file in sorted(folder.rglob('*')):
            if file.is_dir():
                continue
            relative = file.relative_to(prefix).as_posix()
            if root_name == 'lib' and (file.suffix in {'.a', '.la', '.pc'} or '/pkgconfig/' in relative):
                continue
            resolved = file.resolve(strict=True)
            contract.require(resolved.is_relative_to(prefix.resolve()), f'installed symlink escapes prefix: {relative}')
            contract.payload_path(relative)
            contract.require(resolved.is_file(), f'special staged file: {relative}')
            payload[relative] = resolved.read_bytes()
    for command in recipe['commands']:
        binary = prefix / 'bin' / command
        contract.require(binary.is_file(), f'missing exported command: {command}')
        payload['libexec/tp-real/' + command] = binary.read_bytes()
    if name == 'bash':
        binary = payload['libexec/tp-real/bash']
        contract.require((target['prefix'] + '/etc/profile').encode() in binary
                         and b'\0/etc/profile\0' not in binary, 'Bash compiled profile prefix mismatch')
    contract.require(payload, f'empty runtime package: {name}')
    contract.require(set(recipe.get('required_files', [])) <= payload.keys(), f'missing required runtime files: {name}')
    revision, inputs_digest = build_identity()
    manifest = {'schema': 1, 'id': name, 'version': source['version'], 'revision': 1,
                'abi': target['abi'], 'min_android_api': target['min_android_api'],
                'app_id': target['application_id'], 'prefix': target['prefix'],
                'source': {key: source[key] for key in ['upstream', 'revision', 'sha256']},
                'dependencies': recipe['dependencies'], 'licenses': [source['license']],
                'commands': [{'name': cmd, 'kind': 'elf', 'target': 'libexec/tp-real/' + cmd} for cmd in recipe['commands']],
                'files': [{'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'mode': '0644'} for path, data in sorted(payload.items())],
                'patches': recipe['patches'], 'build_id': revision, 'build_inputs_sha256': inputs_digest}
    contract.validate_manifest(manifest, target)
    package_dir = output / 'packages'
    package_dir.mkdir(parents=True, exist_ok=True)
    path = package_dir / f'{name}-{source["version"]}.tpkg'
    temporary = path.with_suffix('.partial')
    with zipfile.ZipFile(temporary, 'w') as archive:
        zip_bytes(archive, 'manifest.json', (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode())
        for file, data in sorted(payload.items()):
            zip_bytes(archive, 'payload/' + file, data)
    contract.load_package(temporary, target)
    temporary.replace(path)
    path.with_suffix('.tpkg.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n')
    return path


def verify_git_layout(manifest, payload, dependencies, target):
    if manifest['id'] != 'git':
        return {}
    expected = {'git', 'git-remote-http', 'git-remote-https', 'git-upload-pack',
                'git-receive-pack', 'git-upload-archive', 'git-shell'}
    contract.require({c['name'] for c in manifest['commands']} == expected, 'Git command inventory mismatch')
    prefix = target['prefix']
    for name in expected:
        path = 'libexec/tp-real/' + name
        contract.require(path in payload, f'missing Git helper: {name}')
        info = contract.inspect_elf(payload[path], executable=True)
        contract.require(info['runpath'] == [prefix + '/lib'], f'Git helper RUNPATH mismatch: {name}')
    binary = payload['libexec/tp-real/git']
    contract.require((prefix + '/bin/bash').encode() + b'\0' in binary, 'Git runtime shell mismatch')
    contract.require((prefix + '/bin').encode() + b'\0' in binary, 'Git managed exec-path mismatch')
    contract.require('share/git-core/templates/info/exclude' in payload, 'Git templates missing')
    packages = {m['id']: (m, data) for m, data in dependencies}
    contract.require({'curl', 'openssl', 'zlib', 'ca-certificates', 'bash'} <= packages.keys(), 'Git dependency closure incomplete')
    curl = packages['curl'][1].get('lib/libcurl.so')
    contract.require(curl is not None and contract.inspect_elf(curl)['soname'] == 'libcurl.so', 'curl Android SONAME/output mismatch')
    http = contract.inspect_elf(payload['libexec/tp-real/git-remote-http'], executable=True)
    contract.require('libcurl.so' in http['needed'], 'Git HTTP helper does not use packaged libcurl.so')
    ca = prefix + '/etc/tls/cert.pem'
    contract.require(ca.encode() + b'\0' in curl, 'curl compiled CA bundle mismatch')
    ca_manifest, ca_payload = packages['ca-certificates']
    certificates = ca_payload.get('etc/tls/cert.pem')
    contract.require(certificates is not None and hashlib.sha256(certificates).hexdigest() == ca_manifest['source']['sha256'], 'CA source/payload checksum mismatch')
    return {'git_layout': 'PASS_STATIC', 'curl_soname': 'libcurl.so', 'https_ca_bundle': ca,
            'managed_exec_path': prefix + '/bin', 'runtime_shell': prefix + '/bin/bash'}


def prepare_gh(source, lock, cache, output, src, stage, target, env, log):
    go = go_toolchain(lock['go'], cache, cache / 'host-go', log)
    modules = Path(os.environ.get('TP_GO_MODULE_CACHE', cache / 'go-modules')).resolve()
    env.update(GOROOT=str(go), TP_GO=str(go / 'bin/go'), GOTOOLCHAIN='local', GOENV='off', GOWORK='off',
               GOFLAGS='-mod=readonly', GOPROXY='https://proxy.golang.org', GOSUMDB='sum.golang.org',
               GONOSUMDB='', GOPRIVATE='', GONOPROXY='', GOVCS='*:off', GOEXPERIMENT='',
               GOTELEMETRY='off', GOMODCACHE=str(modules),
               GOCACHE=os.environ.get('TP_GO_BUILD_CACHE', str(output / 'go-build-cache')),
               GOOS='android', GOARCH='arm64', GOARM64='v8.0', CGO_ENABLED='1', CC=env['TP_CC'],
               CGO_CFLAGS='-O2 -g0', CGO_CPPFLAGS='', CGO_CXXFLAGS='-O2 -g0', CGO_LDFLAGS='',
               TP_VERSION=source['version'], TP_BUILD_DATE=source['build_date'])
    def run(args):
        return subprocess.check_output([env['TP_GO'], *args], cwd=src, env=env, stderr=log, text=True)
    for name in ['go.mod', 'go.sum']:
        check_hash(src / name, source[name.replace('.', '_') + '_sha256'])
    packages = list(json_stream(run(['list', '-deps', '-json', './cmd/gh'])))
    needed = {p['Module']['Path']: p['Module']['Version'] for p in packages
              if p.get('Module') and not p['Module'].get('Main')}
    records = list(json_stream(run(['mod', 'download', '-json', *[name + '@' + version for name, version in sorted(needed.items())]])))
    contract.require({r['Path']: r['Version'] for r in records} == needed, 'Go dependency inventory mismatch')
    verified = verify_go_modules(records, src / 'go.sum')
    log.write(run(['mod', 'verify'])); log.flush()
    files = {}
    prefix = stage / target['prefix'].lstrip('/')
    for record, entry in zip(records, verified):
        directory = Path(record['Dir'])
        licenses = [p for p in directory.iterdir() if p.is_file()
                    and p.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'COPYRIGHT'))]
        contract.require(licenses, 'missing Go module license: ' + record['Path'])
        entry['licenses'] = []
        for license in sorted(licenses):
            relative = 'share/licenses/gh/modules/' + directory.relative_to(modules).as_posix() + '/' + license.name
            contract.payload_path(relative)
            dest = prefix / relative; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(license, dest); entry['licenses'].append(relative)
        ziphash = Path(record['Zip']).with_suffix('.ziphash')
        contract.require(ziphash.read_text().strip() == entry['sum'], 'Go ZIP hash cache mismatch')
        for path in [Path(record[key]) for key in ['Zip', 'GoMod', 'Info']] + [ziphash]:
            contract.require(path.resolve().is_relative_to(modules), 'Go source cache escapes module root')
            relative = 'go-modules/' + path.relative_to(modules).as_posix()
            files[relative] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    license_dir = prefix / 'share/licenses/gh'; license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(go / 'LICENSE', license_dir / 'Go-LICENSE')
    data_dir = prefix / 'share/gh'; data_dir.mkdir(parents=True, exist_ok=True)
    for name in ['go.mod', 'go.sum']:
        check_hash(src / name, source[name.replace('.', '_') + '_sha256'])
        shutil.copyfile(src / name, data_dir / name)
    (output / 'go-inputs.json').write_text(json.dumps({'source_sha256': source['sha256'], 'modules': verified, 'files': files}, indent=2) + '\n')
    # Downloads and Go's automatic compiler substitution are forbidden during compilation.
    env.update(GOPROXY='off', GOSUMDB='off')
    return verified


def finish_gh(source, lock, stage, target, env, modules, log):
    prefix = stage / target['prefix'].lstrip('/')
    binary = prefix / 'bin/gh'
    info = json.loads(subprocess.check_output([env['TP_GO'], 'version', '-m', '-json', str(binary)], env=env, text=True, stderr=log))
    record = {'source_revision': source['revision'], 'source_sha256': source['sha256'],
              'toolchain': lock['go'], 'modules': modules, 'go_info': info,
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    (prefix / 'share/gh/build-inputs.json').write_text(json.dumps(record, indent=2) + '\n')


def verify_gh_layout(manifest, payload, dependencies, target):
    if manifest['id'] != 'gh':
        return {}
    source = json.loads((BASE / 'sources.lock').read_text())['gh']
    toolchain = json.loads((BASE / 'toolchain.lock').read_text())['go']
    contract.require(manifest['commands'] == [{'name': 'gh', 'kind': 'elf', 'target': 'libexec/tp-real/gh'}], 'GH command inventory mismatch')
    contract.require({'git', 'openssh', 'ca-certificates', 'bash'} <= {m['id'] for m, _ in dependencies}, 'GH dependency closure incomplete')
    binary = payload['libexec/tp-real/gh']
    elf = contract.inspect_elf(binary, executable=True)
    contract.require(elf['runpath'] == [target['prefix'] + '/lib'] and 'libc.so' in elf['needed'], 'GH Android dynamic linkage mismatch')
    contract.require((target['prefix'] + '/bin/gh').encode() in binary, 'GH managed self path missing')
    record = contract.read_json(payload['share/gh/build-inputs.json'])
    contract.require(record['toolchain'] == toolchain, 'GH Go toolchain identity mismatch')
    contract.require(record['source_revision'] == source['revision'] == manifest['source']['revision']
                     and record['source_sha256'] == source['sha256'] == manifest['source']['sha256']
                     and manifest['version'] == source['version'], 'GH source identity mismatch')
    contract.require(record['binary_sha256'] == hashlib.sha256(binary).hexdigest(), 'GH build record/binary hash mismatch')
    info = record['go_info']; settings = {s['Key']: s['Value'] for s in info['Settings']}
    contract.require(info['GoVersion'] == toolchain['version'] and info['Path'] == 'github.com/cli/cli/v2/cmd/gh'
                     and all(settings.get(key) == value for key, value in {'GOOS': 'android', 'GOARCH': 'arm64', 'CGO_ENABLED': '1', '-buildmode': 'pie', '-trimpath': 'true'}.items()),
                     'GH Go build settings mismatch')
    for name in ['go.mod', 'go.sum']:
        contract.require(hashlib.sha256(payload['share/gh/' + name]).hexdigest() == source[name.replace('.', '_') + '_sha256'], 'GH module lock mismatch')
    sums = {tuple(line.split()[:2]): line.split()[2] for line in payload['share/gh/go.sum'].decode().splitlines()}
    modules = record['modules']
    contract.require(modules and len({m['path'] for m in modules}) == len(modules), 'GH Go module inventory mismatch')
    for module in modules:
        contract.require(sums.get((module['path'], module['version'])) == module['sum']
                         and sums.get((module['path'], module['version'] + '/go.mod')) == module['go_mod_sum'], 'GH Go module pin mismatch')
        contract.require(module['licenses'] and all(path in payload for path in module['licenses']), 'GH dependency license missing')
    contract.require({(m['path'], m['version'], m['sum']) for m in modules}
                     == {(m['Path'], m['Version'], m['Sum']) for m in info['Deps'] if not m.get('Replace')}
                     and not any(m.get('Replace') for m in info['Deps']), 'GH compiled module closure mismatch')
    contract.require('share/licenses/gh/Go-LICENSE' in payload and 'share/licenses/gh/LICENSE' in payload, 'GH/Go license missing')
    return {'gh_layout': 'PASS_STATIC', 'go_version': info['GoVersion'], 'go_modules': len(modules),
            'managed_self': target['prefix'] + '/bin/gh', 'android_runtime': 'NOT RUN'}


def build(name, sources, recipes, lock, target, cache, output):
    binaries, _ = doctor(lock, target, output)
    requested = [name] if isinstance(name, str) else name
    order = []
    for item in requested:
        order = plan(item, recipes, done=order)
    sysroot = output / 'sysroot'
    # Every requested dependency closure is compiled afresh, including development headers.
    if sysroot.exists():
        shutil.rmtree(sysroot)
    for package_name in order:
        source, recipe = sources[package_name], recipes[package_name]
        logs = output / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / (package_name + '.log'), 'w') as log:
            archive = source_inputs(package_name, source, cache, output, log)
            work = output / 'work' / package_name
            if work.exists():
                shutil.rmtree(work)
            src = work / 'source'
            src.mkdir(parents=True)
            if source.get('format', 'tar') == 'file':
                shutil.copyfile(archive, src / archive.name)
                license = recipe['license_file']
                check_hash(BASE / license['path'], license['sha256'])
                shutil.copyfile(BASE / license['path'], src / 'LICENSE')
            else:
                contract.require(source.get('format', 'tar') == 'tar', 'unsupported source carrier')
                with tarfile.open(archive) as tar:
                    tar.extractall(src, filter='data')
                roots = list(src.iterdir())
                contract.require(len(roots) == 1 and roots[0].is_dir(), 'source archive requires one root directory')
                src = roots[0]
            for patch in recipe['patches']:
                path = BASE / patch['path']
                check_hash(path, patch['sha256'])
                rendered = path.read_text().replace('@TP_PREFIX@', target['prefix'])
                subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1'], input=rendered,
                               text=True, cwd=src, stdout=log, stderr=subprocess.STDOUT, check=True)
            stage = work / 'dest'
            stage.mkdir()
            env = dict(os.environ, TP_SOURCE=str(src), TP_STAGE=str(stage), TP_SYSROOT=str(sysroot),
                       TP_PREFIX=target['prefix'], TP_CC=str(binaries / 'aarch64-linux-android30-clang'),
                       TP_TOOL_BIN=str(binaries), TP_PACKAGE=package_name)
            if package_name == 'gh':
                modules = prepare_gh(source, lock, cache, output, src, stage, target, env, log)
            print(f'BUILD {package_name} {source["version"]} from verified upstream source', flush=True)
            scripts = {'gnu': 'build-gnu.sh', 'core': 'build-core.sh', 'go': 'build-go.sh'}
            script = scripts.get(recipe.get('backend', 'gnu'))
            contract.require(script is not None, 'unsupported recipe backend')
            subprocess.run(['bash', str(BASE / 'recipes' / script)], cwd=work, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            if package_name == 'gh':
                finish_gh(source, lock, stage, target, env, modules, log)
            prefix = stage / target['prefix'].lstrip('/')
            license_files = [p for p in src.iterdir() if p.is_file() and p.name in {'COPYING', 'COPYING.LESSER', 'COPYRIGHT', 'LICENSE', 'LICENSE.txt', 'LICENCE'}]
            contract.require(license_files, f'missing source license text: {package_name}')
            license_dir = prefix / 'share/licenses' / package_name
            license_dir.mkdir(parents=True, exist_ok=True)
            for license_file in license_files:
                shutil.copyfile(license_file, license_dir / license_file.name)
            shutil.copytree(prefix, sysroot / target['prefix'].lstrip('/'), dirs_exist_ok=True, symlinks=True)
            artifact = package(package_name, source, recipe, stage, target, output)
            dependencies = [contract.load_package(output / 'packages' / f'{dep}-{sources[dep]["version"]}.tpkg', target) for dep in plan(package_name, recipes)[:-1]]
            manifest, payload = contract.load_package(artifact, target)
            report = contract.verify_dependencies(manifest, payload, dependencies)
            report.update(verify_git_layout(manifest, payload, dependencies, target))
            report.update(verify_gh_layout(manifest, payload, dependencies, target))
            (logs / (package_name + '-verify.json')).write_text(json.dumps(report, indent=2) + '\n')
            shutil.rmtree(work)
            print(f'PACKAGE {artifact.name}: PASS_STATIC; Android runtime NOT RUN', flush=True)
    return order


def bootstrap(order, sources, target, output):
    index = {'schema': 1, 'app_id': target['application_id'], 'prefix': target['prefix'],
             'abi': target['abi'], 'min_android_api': target['min_android_api'], 'packages': []}
    owners, commands, packages = {}, set(), []
    for name in order:
        path = output / 'packages' / f'{name}-{sources[name]["version"]}.tpkg'
        manifest, payload = contract.load_package(path, target)
        for file, data in payload.items():
            contract.require(file not in owners, f'cross-package file collision: {file}')
            owners[file] = name
        for command in manifest['commands']:
            contract.require(command['name'] not in commands, f'command collision: {command["name"]}')
            commands.add(command['name'])
        entry = {'id': name, 'path': 'packages/' + path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        index['packages'].append(entry)
        packages.append(path)
    path = output / 'bootstrap.zip'
    with zipfile.ZipFile(path.with_suffix('.partial'), 'w') as archive:
        zip_bytes(archive, 'index.json', (json.dumps(index, sort_keys=True, indent=2) + '\n').encode())
        for package_path in packages:
            zip_bytes(archive, 'packages/' + package_path.name, package_path.read_bytes())
    path.with_suffix('.partial').replace(path)
    (output / 'bootstrap.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '  bootstrap.zip\n')
    print(json.dumps({'bootstrap': str(path), 'packages': order, 'status': 'PASS_STATIC', 'android_runtime': 'NOT RUN'}))
    return path


def source_offer(order, sources, cache, output):
    """Ship exact upstream inputs and build scripts alongside GPL binaries."""
    output.mkdir(parents=True, exist_ok=True)
    inputs = {}
    with open(output / 'source-verification.log', 'w') as log:
        for name in order:
            source = sources[name]
            archive = source_inputs(name, source, cache, output, log)
            inputs['upstream/' + archive.name] = archive.read_bytes()
            if source.get('signature_url'):
                signature = cache / source['signature_url'].rsplit('/', 1)[1]
                inputs['upstream/' + signature.name] = signature.read_bytes()
    if 'gh' in order:
        go_lock = json.loads((BASE / 'toolchain.lock').read_text())['go']
        compiler = fetch(go_lock['url'], cache / go_lock['url'].rsplit('/', 1)[1], go_lock['sha256'])
        inputs['upstream/' + compiler.name] = compiler.read_bytes()
        go_inputs = json.loads((output / 'go-inputs.json').read_text())
        contract.require(go_inputs['source_sha256'] == sources['gh']['sha256'], 'stale Go source inventory; build gh first')
        for relative, item in go_inputs['files'].items():
            contract.require(not PurePosixPath(relative).is_absolute() and '..' not in PurePosixPath(relative).parts, 'unsafe Go source inventory path')
            path = Path(item['path']); check_hash(path, item['sha256'])
            inputs['upstream/' + relative] = path.read_bytes()
    tracked = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z', 'shared', 'termux-pro-builder'], text=True)
    for relative in tracked.split('\0'):
        if relative and '__pycache__' not in relative:
            inputs['build/' + relative] = (ROOT / relative).read_bytes()
    for name in ['PACKAGE_CONTRACT.md', 'BUILDER_SPEC.md', 'ARCHITECTURE.md']:
        inputs['build/' + name] = (ROOT / name).read_bytes()
    revision, digest = build_identity()
    record = {'schema': 1, 'build_id': revision, 'build_inputs_sha256': digest,
              'packages': order, 'files': {name: hashlib.sha256(data).hexdigest()
                                         for name, data in sorted(inputs.items())}}
    inputs['index.json'] = (json.dumps(record, indent=2, sort_keys=True) + '\n').encode()
    inputs['README.txt'] = (
        'Corresponding source for the accompanying Termux Pro candidate packages.\n'
        'Official, unchanged upstream archives and detached signatures: upstream/.\n'
        'Build scripts, patches, locks, keys and contract: build/.\n'
        'Extract archives into a source cache and follow build/termux-pro-builder/README.md.\n'
        'The pinned Android NDK and listed host build tools must be installed separately.\n'
        'Source license texts are in the upstream archives and runtime package payloads.\n'
        'Android execution and release approval are not implied by this source bundle.\n').encode()
    path = output / 'sources.zip'
    with zipfile.ZipFile(path.with_suffix('.partial'), 'w') as archive:
        for name, data in sorted(inputs.items()):
            zip_bytes(archive, name, data)
    path.with_suffix('.partial').replace(path)
    path.with_suffix('.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '  sources.zip\n')
    return path


def main(args):
    contract.require(args, 'usage: build.sh doctor | build PACKAGE | bootstrap | source-offer | verify FILE | test PACKAGE | release')
    target = contract.read_json((ROOT / 'shared/target.json').read_text())
    sources = contract.read_json((BASE / 'sources.lock').read_text())
    lock = contract.read_json((BASE / 'toolchain.lock').read_text())
    recipes = {p.stem: contract.read_json(p.read_text()) for p in (BASE / 'recipes').glob('*.json')}
    output = Path(os.environ.get('TP_OUTPUT_DIR', str(BASE / 'output'))).resolve()
    cache = Path(os.environ.get('TP_SOURCE_CACHE', str(BASE / 'cache'))).resolve()
    command = args[0]
    if command == 'doctor' and len(args) == 1:
        print(json.dumps(doctor(lock, target, output)[1], indent=2))
    elif command == 'build' and len(args) == 2:
        build(args[1], sources, recipes, lock, target, cache, output)
    elif command == 'bootstrap':
        order = build(args[1:] or ['bash'], sources, recipes, lock, target, cache, output)
        bootstrap(order, sources, target, output)
        source_offer(order, sources, cache, output)
    elif command == 'source-offer':
        order = []
        for name in args[1:] or ['bash']:
            order = plan(name, recipes, done=order)
        print(source_offer(order, sources, cache, output))
    elif command in {'verify', 'test'} and len(args) == 2:
        path = Path(args[1]) if command == 'verify' else output / 'packages' / f'{args[1]}-{sources[args[1]]["version"]}.tpkg'
        manifest, payload = contract.load_package(path, target)
        order = plan(manifest['id'], recipes)[:-1]
        dependencies = [contract.load_package(output / 'packages' / f'{dep}-{sources[dep]["version"]}.tpkg', target) for dep in order]
        report = contract.verify_dependencies(manifest, payload, dependencies)
        report.update(verify_git_layout(manifest, payload, dependencies, target))
        report.update(verify_gh_layout(manifest, payload, dependencies, target))
        print(json.dumps(report, indent=2))
    elif command == 'release':
        raise ValueError('release BLOCKED: E2/E3/device/package/host-image/license/distribution gates are not approved; candidate artifacts are not a release')
    else:
        raise ValueError('unsupported command/arguments')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)[:1800], 'hint': 'See output/logs for build diagnostics; no failed gate was promoted.'}), file=sys.stderr)
        sys.exit(1)
