#!/usr/bin/env python3
"""Source-only Android package builds; no target package repository or plugin DSL."""
import hashlib
import json
import os
from pathlib import Path
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
        try:
            with urllib.request.urlopen(url, timeout=90) as source, open(partial, 'wb') as output:
                shutil.copyfileobj(source, output)
            check_hash(partial, digest)
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    check_hash(path, digest)
    return path


def doctor(lock, target, output):
    contract.require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'build host must be Linux x86-64')
    for tool in ['make', 'patch', 'gcc', 'gpg', 'tic']:
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


def source_inputs(name, source, cache, output, log):
    archive = fetch(source['url'], cache / source['url'].rsplit('/', 1)[1], source['sha256'])
    if source.get('signature_url'):
        signature = fetch(source['signature_url'], cache / source['signature_url'].rsplit('/', 1)[1], source['signature_sha256'])
        home = output / 'gpg-home'
        home.mkdir(mode=0o700, exist_ok=True)
        command = ['gpg', '--homedir', str(home), '--batch', '--no-default-keyring',
                   '--keyring', str(BASE / 'vendor/gnu-signers.gpg'), '--status-fd', '1',
                   '--verify', str(signature), str(archive)]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write(result.stdout); log.flush()
        statuses = result.stdout.splitlines()
        contract.require(result.returncode == 0 and any(line.startswith('[GNUPG:] VALIDSIG ' + source['signer'] + ' ') for line in statuses), f'source signature verification failed: {name}')
        contract.require(not any(any(f'[GNUPG:] {tag} ' in line for tag in ['EXPKEYSIG', 'REVKEYSIG', 'BADSIG', 'ERRSIG', 'EXPSIG']) for line in statuses), f'unacceptable source signature: {name}')
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


def build(name, sources, recipes, lock, target, cache, output):
    binaries, _ = doctor(lock, target, output)
    order = plan(name, recipes)
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
            print(f'BUILD {package_name} {source["version"]} from verified upstream source', flush=True)
            subprocess.run(['bash', str(BASE / 'recipes/build-gnu.sh')], cwd=work, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            prefix = stage / target['prefix'].lstrip('/')
            license_files = [p for p in src.iterdir() if p.is_file() and p.name in {'COPYING', 'COPYING.LESSER', 'COPYRIGHT', 'LICENSE', 'AUTHORS'}]
            license_dir = prefix / 'share/licenses' / package_name
            license_dir.mkdir(parents=True, exist_ok=True)
            for license_file in license_files:
                shutil.copyfile(license_file, license_dir / license_file.name)
            shutil.copytree(prefix, sysroot / target['prefix'].lstrip('/'), dirs_exist_ok=True, symlinks=True)
            artifact = package(package_name, source, recipe, stage, target, output)
            dependencies = [contract.load_package(output / 'packages' / f'{dep}-{sources[dep]["version"]}.tpkg', target) for dep in plan(package_name, recipes)[:-1]]
            manifest, payload = contract.load_package(artifact, target)
            report = contract.verify_dependencies(manifest, payload, dependencies)
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


def main(args):
    contract.require(args, 'usage: build.sh doctor | build PACKAGE | bootstrap | verify FILE | test PACKAGE | release')
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
    elif command == 'bootstrap' and len(args) == 1:
        order = build('bash', sources, recipes, lock, target, cache, output)
        bootstrap(order, sources, target, output)
    elif command in {'verify', 'test'} and len(args) == 2:
        path = Path(args[1]) if command == 'verify' else output / 'packages' / f'{args[1]}-{sources[args[1]]["version"]}.tpkg'
        manifest, payload = contract.load_package(path, target)
        order = plan(manifest['id'], recipes)[:-1]
        dependencies = [contract.load_package(output / 'packages' / f'{dep}-{sources[dep]["version"]}.tpkg', target) for dep in order]
        print(json.dumps(contract.verify_dependencies(manifest, payload, dependencies), indent=2))
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
