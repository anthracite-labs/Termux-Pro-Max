"""Orchestration tests use fake adb; these are never device runtime evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class TerminalOrchestration(unittest.TestCase):
    def run_fixture(self, runner='OK (1 test)', status='PASS_THIS_DEVICE', close='PASS', abi='arm64-v8a', policy='Enforcing'):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'ci').mkdir()
            shutil.copyfile(ROOT / 'ci/run-terminal-acceptance.sh', folder / 'ci/run-terminal-acceptance.sh')
            adb = folder / 'adb'
            adb.write_text('#!' + sys.executable + '\n' + '''
import json, os, sys
args = sys.argv[1:]
with open(os.environ['TP_CALLS'], 'a') as calls: calls.write(' '.join(args) + '\\n')
if args[:3] == ['shell', 'getprop', 'ro.product.cpu.abi']: print(os.environ['TP_ABI'])
elif args[:2] == ['shell', 'getenforce']: print(os.environ['TP_POLICY'])
elif args[:3] == ['shell', 'am', 'instrument']: print(os.environ['TP_RUNNER'])
elif args[0] == 'exec-out': print(os.environ['TP_RESULT'])
else: print('fake adb')
'''); adb.chmod(0o755)
            apk = folder / 'app.apk'
            with zipfile.ZipFile(apk, 'w') as archive: archive.writestr('assets/build.json', '{}')
            test_apk = folder / 'test.apk'; test_apk.write_bytes(b'host-only-fixture')
            record = {'status': status, 'fixture': 'bundled-bash-pty-v1', 'close_reap': close, 'E3': 'NOT RUN'}
            calls = folder / 'calls'
            env = dict(os.environ, PATH=directory + ':' + os.environ['PATH'], TP_RUNNER=runner,
                       TP_RESULT=json.dumps(record), TP_ABI=abi, TP_POLICY=policy, TP_CALLS=str(calls))
            result = subprocess.run(['bash', str(folder / 'ci/run-terminal-acceptance.sh'), str(apk), str(test_apk)],
                                    env=env, capture_output=True, text=True, timeout=20)
            status_text = (folder / 'build/evidence/terminal-device/status.txt').read_text()
            return result, status_text, calls.read_text()

    def test_both_runner_and_structured_result_are_required(self):
        result, status, calls = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('terminal_runtime=PASS (', status)
        self.assertIn('rm -f files/acceptance/terminal-result.json', calls)
        self.assertLess(calls.index('rm -f'), calls.index('shell am instrument'))
        for fields in [{'runner': 'FAILURES!!!'}, {'status': 'NOT_RUN'}, {'close': 'NOT_RUN'}]:
            with self.subTest(fields=fields):
                result, status, _ = self.run_fixture(**fields)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('terminal_runtime=UNVERIFIED', status)

    def test_wrong_abi_cannot_run_or_pass(self):
        result, status, calls = self.run_fixture(abi='x86_64')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('shell am instrument', calls)
        self.assertIn('terminal_runtime=UNVERIFIED', status)

    def test_environment_guards_fail_before_install_and_preserve_failure_status(self):
        for fields in [{'abi': ''}, {'abi': 'arm64*'}, {'policy': ''},
                       {'policy': '*'}, {'policy': 'Permissive'}]:
            with self.subTest(fields=fields):
                result, status, calls = self.run_fixture(**fields)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn('install -r', calls)
                self.assertNotIn('shell am instrument', calls)
                self.assertIn('terminal_runtime=UNVERIFIED', status)
                self.assertIn('exit_code=1', status)
