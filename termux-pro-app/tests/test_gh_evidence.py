"""Host-only checks of evidence policy, not Android/GH execution evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest
import http.client
import http.server
import json
import threading

PATH = Path(__file__).resolve().parents[1] / 'ci/run-gh-acceptance.py'


class GhEvidence(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('gh_acceptance', PATH)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def test_complete_matching_chain_and_rejection_of_unverified_or_stale_results(self):
        prefix = '/data/user/0/com.anthracitelabs.termuxpro/files/usr'
        reference = {'build': {'source_revision': 'a' * 40, 'bootstrap_sha256': 'b' * 64},
                     'commands': {name: 'c' * 64 for name in ['bash', 'gh', 'git', 'ssh']},
                     'manifests': {name: 'd' * 64 for name in ['bash', 'gh', 'git', 'openssh']},
                     'prefix': prefix, 'run': 'unique-run'}
        record = dict(reference, status='PASS_THIS_DEVICE', fixture='source-gh-git-ssh-clone-v1',
                      expected_commit='e' * 40, actual_commit='e' * 40, gh_exit=0,
                      api=36, target_sdk=36, abi='arm64-v8a', page_size=4096, gh_pid=4321)
        trace = [{'event': 'cmd_name', 'sid': 'git-session', 'name': 'clone'},
                 {'event': 'child_start', 'sid': 'git-session', 'child_id': 0, 'child_class': 'transport/ssh', 'argv': [prefix + '/bin/ssh']},
                 {'event': 'child_exit', 'sid': 'git-session', 'child_id': 0, 'code': 0, 'pid': 4323},
                 {'event': 'exit', 'sid': 'git-session', 'code': 0}]
        self.module.check_evidence(record, trace, reference, 'e' * 40)
        for field, value in [('status', 'NOT RUN'), ('actual_commit', 'f' * 40), ('gh_exit', 1),
                             ('abi', 'x86_64'), ('build', {}), ('commands', {}), ('manifests', {}), ('gh_pid', 0), ('run', 'stale-run')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.module.check_evidence(dict(record, **{field: value}), trace, reference, 'e' * 40)
        for index, field, value in [(1, 'argv', ['/fake/ssh']), (2, 'code', 255), (3, 'code', 128), (2, 'pid', 0)]:
            bad = copy.deepcopy(trace); bad[index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                self.module.check_evidence(record, bad, reference, 'e' * 40)
        with self.assertRaises(ValueError): self.module.check_evidence(record, [], reference, 'e' * 40)

    def test_loopback_api_fixture_only_answers_the_expected_repository(self):
        url = 'ssh://fixture@127.0.0.1:38222/tmp/fixture.git'
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), self.module.api_handler(url))
        thread = threading.Thread(target=server.serve_forever); thread.start()
        try:
            for owner, status in [('e3', 200), ('unexpected', 400)]:
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                request = json.dumps({'query': 'query RepositoryInfo', 'variables': {'owner': owner, 'name': 'fixture'}})
                connection.request('POST', '/api/graphql', request, {'Content-Type': 'application/json'})
                response = connection.getresponse(); body = response.read(); connection.close()
                self.assertEqual(response.status, status)
                if status == 200: self.assertEqual(json.loads(body)['data']['repository']['sshUrl'], url)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
