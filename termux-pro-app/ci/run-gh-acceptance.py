#!/usr/bin/env python3
"""Physical ARM64 device only. A local API stub is data; GH/Git/SSH are real packages."""
import argparse
import hashlib
import http.server
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'shared'))
import contract

APP = 'com.anthracitelabs.termuxpro'


def check_evidence(record, trace, reference, expected_commit):
    contract.require(record['status'] == 'PASS_THIS_DEVICE' and record['fixture'] == 'source-gh-git-ssh-clone-v1', 'unverified E3 result')
    contract.require(record['expected_commit'] == record['actual_commit'] == expected_commit and record['gh_exit'] == 0, 'clone did not return the expected commit')
    contract.require(record['abi'] == 'arm64-v8a' and record['api'] >= 30 and record['target_sdk'] >= 36
                     and record['page_size'] in {4096, 16384} and record['gh_pid'] > 0, 'unsupported device/process evidence')
    for field in ['build', 'commands', 'manifests', 'prefix', 'run']:
        contract.require(record[field] == reference[field], 'APK/package evidence mismatch: ' + field)
    clones = {e['sid'] for e in trace if e.get('event') == 'cmd_name' and e.get('name') == 'clone'}
    ssh = {(e['sid'], e['child_id']) for e in trace if e.get('event') == 'child_start' and e.get('sid') in clones
           and e.get('child_class') == 'transport/ssh' and e.get('argv') and e['argv'][0] == reference['prefix'] + '/bin/ssh'}
    finished = {(e['sid'], e['child_id']) for e in trace if e.get('event') == 'child_exit'
                and e.get('code') == 0 and e.get('pid', 0) > 0}
    exited = {e['sid'] for e in trace if e.get('event') == 'exit' and e.get('code') == 0}
    contract.require(any(key in finished and key[0] in exited for key in ssh), 'missing successful real Git-to-managed-SSH trace')


def apk_reference(apk):
    with zipfile.ZipFile(apk) as outer:
        build = contract.read_json(outer.read('assets/build.json'))
        target = contract.read_json(outer.read('assets/target.json'))
        data = outer.read('assets/bootstrap.zip')
        contract.require(hashlib.sha256(data).hexdigest() == build['bootstrap_sha256']
                         == outer.read('assets/bootstrap.sha256').decode().strip(), 'APK bootstrap hash mismatch')
    packages, manifests = [], {}
    with zipfile.ZipFile(io.BytesIO(data)) as bootstrap:
        index = contract.read_json(bootstrap.read('index.json'))
        for entry in index['packages']:
            data = bootstrap.read(entry['path'])
            contract.require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'bootstrap package hash mismatch')
            packages.append(contract.load_package(io.BytesIO(data), target))
            contract.require(packages[-1][0]['id'] == entry['id'], 'bootstrap package identity mismatch')
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                if entry['id'] in {'bash', 'gh', 'git', 'openssh'}:
                    manifests[entry['id']] = hashlib.sha256(package.read('manifest.json')).hexdigest()
    for manifest, payload in packages:
        contract.verify_dependencies(manifest, payload, [(m, p) for m, p in packages if m['id'] != manifest['id']])
    commands = {c['name']: hashlib.sha256(p[c['target']]).hexdigest()
                for m, p in packages for c in m['commands'] if c['name'] in {'bash', 'gh', 'git', 'ssh'}}
    contract.require(set(commands) == {'bash', 'gh', 'git', 'ssh'} and len(manifests) == 4, 'APK lacks source-built chain')
    return {'build': build, 'commands': commands, 'manifests': manifests, 'prefix': target['prefix']}


def api_handler(ssh_url):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never record HTTP authorization headers, even for fixture credentials.

        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if self.path != '/api/graphql' or not 0 < size < 65536:
                self.send_error(400); return
            request = json.loads(self.rfile.read(size))
            if 'RepositoryInfo' not in request.get('query', '') or request.get('variables') != {'owner': 'e3', 'name': 'fixture'}:
                self.send_error(400); return
            body = json.dumps({'data': {'repository': {'id': 'E3Fixture', 'databaseId': 1,
                'name': 'fixture', 'owner': {'login': 'e3'}, 'sshUrl': ssh_url,
                'defaultBranchRef': {'name': 'main'}, 'parent': None, 'hasWikiEnabled': False}}}).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path); parser.add_argument('test_apk', type=Path)
    parser.add_argument('lab', type=Path, help='disposable loopback SSH fixture configuration; see docs/testing/gh-e3.md')
    args = parser.parse_args()
    lab = contract.read_json(args.lab.read_bytes())
    match = re.fullmatch(r'ssh://[A-Za-z0-9_.-]+@127\.0\.0\.1:([0-9]{1,5})/[A-Za-z0-9_./-]+', lab['ssh_url'])
    contract.require(match is not None and 1024 <= int(match[1]) <= 65535
                     and isinstance(lab['ssh_host_port'], int) and 1024 <= lab['ssh_host_port'] <= 65535, 'SSH fixture must use unprivileged loopback ports')
    contract.require(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', lab['expected_commit']) is not None, 'expected commit must be immutable')
    key, known = Path(lab['key']), Path(lab['known_hosts'])
    contract.require('termux-pro-e3-fixture' in Path(str(key) + '.pub').read_text(), 'use a freshly generated disposable E3 key')
    reference = apk_reference(args.apk)
    token = uuid.uuid4().hex; socket = 'tp-gh-e3-' + token
    reference['run'] = token
    relative = 'files/acceptance/gh-e3/' + token
    evidence = Path(__file__).resolve().parents[1] / 'build/evidence/gh-device' / token
    evidence.mkdir(parents=True)
    status = {'E3': 'NOT RUN', 'run': token}; server = None; owned = []
    (evidence / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    def adb(*argv, timeout=30, data=None, check=True):
        return subprocess.run(['adb', *argv], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=check).stdout
    try:
        abi = adb('shell', 'getprop', 'ro.product.cpu.abi').decode().strip()
        contract.require(abi == 'arm64-v8a' and adb('shell', 'getenforce').decode().strip() == 'Enforcing', 'requires enforcing ARM64 Android')
        (evidence / 'environment.json').write_text(json.dumps({'apk_sha256': hashlib.sha256(args.apk.read_bytes()).hexdigest(),
            'test_apk_sha256': hashlib.sha256(args.test_apk.read_bytes()).hexdigest(), 'reference': reference,
            'api': adb('shell', 'getprop', 'ro.build.version.sdk').decode().strip(),
            'page_size': adb('shell', 'getconf', 'PAGESIZE').decode().strip()} , indent=2) + '\n')
        adb('install', '-r', str(args.apk), timeout=90); adb('install', '-r', str(args.test_apk), timeout=90)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), api_handler(lab['ssh_url']))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for remote, local in [('localabstract:' + socket, 'tcp:' + str(server.server_port)),
                              ('tcp:' + match[1], 'tcp:' + str(lab['ssh_host_port']))]:
            adb('reverse', '--no-rebind', remote, local); owned.append(remote)
        adb('shell', 'run-as', APP, 'mkdir', '-p', relative)
        for name, path in [('id_ed25519', key), ('known_hosts', known)]:
            adb('exec-in', 'run-as', APP, '/system/bin/dd', 'of=' + relative + '/' + name, data=path.read_bytes())
            adb('shell', 'run-as', APP, 'chmod', '600', relative + '/' + name)
        result = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', APP + '.GhChainAcceptance',
                     '-e', 'e3_run', token, '-e', 'e3_socket', socket, '-e', 'e3_ssh_url', lab['ssh_url'],
                     '-e', 'e3_expected_commit', lab['expected_commit'], APP + '.test/androidx.test.runner.AndroidJUnitRunner', timeout=240)
        (evidence / 'instrumentation.log').write_bytes(result)
        contract.require(re.search(rb'^OK \(1 test\)', result, re.M) is not None, 'Android instrumentation failed or did not run')
        for name in ['result.json', 'git-trace.jsonl', 'gh.log']:
            (evidence / name).write_bytes(adb('exec-out', 'run-as', APP, 'cat', relative + '/' + name))
        record = json.loads((evidence / 'result.json').read_text())
        trace = [json.loads(line) for line in (evidence / 'git-trace.jsonl').read_text().splitlines()]
        check_evidence(record, trace, reference, lab['expected_commit'])
        status['E3'] = 'PASS_THIS_DEVICE'
    except Exception:
        status['E3'] = 'UNVERIFIED'; raise
    finally:
        for name in ['result.json', 'git-trace.jsonl', 'gh.log']:
            try: (evidence / name).write_bytes(adb('exec-out', 'run-as', APP, 'cat', relative + '/' + name))
            except (subprocess.SubprocessError, OSError): pass
        try: (evidence / 'logcat.log').write_bytes(adb('logcat', '-d', '-v', 'threadtime', '-s', 'termux-pro:*', 'AndroidRuntime:*'))
        except (subprocess.SubprocessError, OSError): pass
        for remote in reversed(owned):
            try: adb('reverse', '--remove', remote, check=False)
            except (subprocess.SubprocessError, OSError): status.setdefault('cleanup_errors', []).append(remote)
        if server is not None: server.shutdown(); server.server_close()
        status.update(E2='SEPARATE_PROOF_REQUIRED', terminal_acceptance='SEPARATE_PROOF_REQUIRED')
        (evidence / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
        print(evidence)


if __name__ == '__main__':
    main()
