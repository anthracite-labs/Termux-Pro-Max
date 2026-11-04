"""Package v1 trust-boundary checks shared by source-builder host tools."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import stat
import struct
import zipfile

MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 20000
PLATFORM_LIBRARIES = {'libc.so', 'libm.so', 'libdl.so', 'liblog.so', 'libandroid.so'}
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9+_.-]{0,63}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def payload_path(value):
    require(isinstance(value, str) and value, 'empty/non-string path')
    require('\\' not in value and not any(ord(c) < 32 for c in value), 'unsafe path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value, 'noncanonical path')
    require(all(p not in {'', '.', '..'} for p in value.split('/')), 'path traversal')
    require(path.parts[0] in {'lib', 'libexec', 'share', 'etc'}, 'unmanaged payload root')
    return value


def inspect_elf(data, executable=False):
    require(len(data) >= 64 and data[:7] == b'\x7fELF\x02\x01\x01', 'expected ELF64 little-endian')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    kind, machine, entry, phoff, phsize, count = header[1], header[2], header[4], header[5], header[9], header[10]
    require(kind == 3 and machine == 183, 'expected AArch64 ET_DYN/PIE')
    require(phsize == 56 and 0 < count <= 128 and phoff + count * 56 <= len(data), 'invalid ELF program headers')
    loads, dynamic, interpreter = [], None, None
    for i in range(count):
        tag, flags, offset, address, _, size, memory, alignment = struct.unpack_from('<IIQQQQQQ', data, phoff + i * 56)
        require(offset + size <= len(data) and memory >= size, 'invalid ELF segment bounds')
        if tag == 1:
            require(alignment >= 16384 and alignment & (alignment - 1) == 0,
                    'ELF load alignment is not 16 KB compatible')
            require((offset - address) % 16384 == 0 and flags & 3 != 3, 'invalid/WX ELF load segment')
            loads.append((offset, address, size, memory, flags))
        elif tag == 2:
            require(dynamic is None and size % 16 == 0, 'invalid dynamic segment')
            dynamic = data[offset:offset + size]
        elif tag == 3:
            require(interpreter is None, 'duplicate ELF interpreter')
            interpreter = data[offset:offset + size]
    require(loads and dynamic is not None, 'static ELF is unsupported')
    if executable:
        require(interpreter == b'/system/bin/linker64\0', 'unsupported executable interpreter')
        require(entry and any(a <= entry < a + n and f & 1 for _, a, _, n, f in loads), 'missing executable entry')
    tags = []
    for tag, value in struct.iter_unpack('<qQ', dynamic):
        if tag == 0:
            break
        require(tag != 22 and not (tag == 30 and value & 4), 'ELF text relocations are unsupported')
        tags.append((tag, value))
    values = dict(tags)
    strings = None
    if 5 in values and 10 in values:
        for offset, address, size, _, _ in loads:
            if address <= values[5] and values[5] + values[10] <= address + size:
                start = offset + values[5] - address
                strings = data[start:start + values[10]]
                break
    require(strings is not None, 'ELF dynamic string table is missing')
    def string(index):
        require(index < len(strings) and b'\0' in strings[index:], 'invalid ELF dynamic string')
        return strings[index:strings.index(b'\0', index)].decode('utf-8')
    needed = [string(value) for tag, value in tags if tag == 1]
    require(all('/' not in name for name in needed), 'absolute DT_NEEDED path')
    runpath = [string(value) for tag, value in tags if tag in {15, 29}]
    return {'needed': needed, 'runpath': runpath}


def validate_manifest(manifest, target):
    require(isinstance(manifest, dict), 'manifest must be an object')
    required = {'schema', 'id', 'version', 'revision', 'abi', 'min_android_api', 'app_id',
                'prefix', 'source', 'dependencies', 'commands', 'files', 'licenses'}
    require(required <= manifest.keys() and type(manifest['schema']) is int and manifest['schema'] == 1, 'unsupported/incomplete manifest schema')
    for name in ['id', 'version']:
        require(isinstance(manifest[name], str) and IDENTIFIER.fullmatch(manifest[name]) and '..' not in manifest[name], f'invalid {name}')
    require(type(manifest['revision']) is int and manifest['revision'] > 0, 'invalid revision')
    for field, expected in [('abi', target['abi']), ('app_id', target['application_id']),
                            ('prefix', target['prefix']), ('min_android_api', target['min_android_api'])]:
        require(type(manifest[field]) is type(expected) and manifest[field] == expected, f'{field} mismatch')
    source = manifest['source']
    require(isinstance(source, dict) and all(isinstance(source.get(k), str) for k in ['upstream', 'revision', 'sha256']), 'invalid source provenance')
    require(source['upstream'].startswith('https://') and source['revision'] not in {'main', 'master', 'HEAD', 'latest'} and source['revision'], 'source must be pinned')
    require(DIGEST.fullmatch(source['sha256']), 'invalid source checksum')
    require(isinstance(manifest['licenses'], list) and manifest['licenses'] and all(isinstance(x, str) and x for x in manifest['licenses']), 'missing licenses')
    dependencies = manifest['dependencies']
    require(isinstance(dependencies, list) and all(isinstance(x, str) and IDENTIFIER.fullmatch(x) for x in dependencies), 'invalid dependencies')
    require(len(dependencies) == len(set(dependencies)) and manifest['id'] not in dependencies, 'duplicate/self dependency')
    require(isinstance(manifest['files'], list) and isinstance(manifest['commands'], list), 'invalid inventory/commands')
    inventory = {}
    for item in manifest['files']:
        require(isinstance(item, dict) and set(item) == {'path', 'sha256', 'mode'}, 'invalid file entry')
        path = payload_path(item['path'])
        require(path not in inventory, f'duplicate path: {path}')
        require(isinstance(item['sha256'], str) and DIGEST.fullmatch(item['sha256']), 'invalid file digest')
        require(isinstance(item['mode'], str) and item['mode'] in {'0644', '0755'}, 'unsupported file mode')
        inventory[path] = item
    commands = set()
    for item in manifest['commands']:
        require(isinstance(item, dict) and set(item) == {'name', 'kind', 'target'}, 'invalid command entry')
        name = item['name']
        require(isinstance(name, str) and IDENTIFIER.fullmatch(name) and '..' not in name and name not in commands, 'invalid/duplicate command')
        require(item['kind'] == 'elf' and item['target'] == f'libexec/tp-real/{name}' and item['target'] in inventory, 'unsupported command target/kind')
        commands.add(name)
    return manifest


def load_package(path, target):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        require(len(infos) <= MAX_FILES and len(names) == len(set(names)), 'duplicate/excessive ZIP entries')
        require(sum(i.file_size for i in infos) <= MAX_BYTES and all(i.file_size <= MAX_BYTES // 2 for i in infos), 'oversized package')
        for info in infos:
            mode = info.external_attr >> 16
            require(not info.flag_bits & 1 and not info.is_dir(), 'encrypted/directory ZIP entry')
            require(stat.S_IFMT(mode) in {0, stat.S_IFREG}, 'special/symlink ZIP entry')
            require(info.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}, 'unsupported ZIP compression')
        require('manifest.json' in names, 'missing manifest')
        require(archive.getinfo('manifest.json').file_size <= 4 * 1024 * 1024, 'oversized manifest')
        manifest = validate_manifest(read_json(archive.read('manifest.json')), target)
        expected = {'payload/' + f['path'] for f in manifest['files']} | {'manifest.json'}
        require(set(names) == expected, 'archive/inventory mismatch')
        payload = {}
        for item in manifest['files']:
            data = archive.read('payload/' + item['path'])
            require(hashlib.sha256(data).hexdigest() == item['sha256'], f'payload checksum mismatch: {item["path"]}')
            mode = archive.getinfo('payload/' + item['path']).external_attr >> 16
            require(not stat.S_IMODE(mode) or stat.S_IMODE(mode) == int(item['mode'], 8), 'payload mode mismatch')
            require(not any(x in data for x in [b'/data/data/com.termux/', b'/data/user/0/com.termux/', b'/workspace/']), f'foreign/host path in {item["path"]}')
            payload[item['path']] = data
        for command in manifest['commands']:
            inspect_elf(payload[command['target']], executable=True)
        for name, data in payload.items():
            if data.startswith(b'\x7fELF'):
                result = inspect_elf(data)
                require(all(p == target['prefix'] + '/lib' for group in result['runpath'] for p in group.split(':')), f'unsupported RUNPATH in {name}')
        return manifest, payload


def verify_dependencies(manifest, payload, dependency_packages):
    dependencies = {m['id']: (m, data) for m, data in dependency_packages}
    require(set(manifest['dependencies']) <= dependencies.keys(), 'missing declared dependency')
    libraries = PLATFORM_LIBRARIES | {PurePosixPath(path).name for path in payload if path.startswith('lib/')}
    for _, data in dependencies.values():
        libraries.update(PurePosixPath(path).name for path in data if path.startswith('lib/'))
    for path, data in payload.items():
        if data.startswith(b'\x7fELF'):
            needed = set(inspect_elf(data)['needed'])
            require(needed <= libraries, f'missing DT_NEEDED for {path}: {sorted(needed - libraries)}')
    return {'status': 'PASS_STATIC', 'package': manifest['id'], 'files': len(payload),
            'android_runtime': 'NOT RUN', 'dependencies': sorted(dependencies)}
