"""Host checks for CI orchestration; these never count as Android evidence."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AndroidCi(unittest.TestCase):
    def run_proof(self, report, abi='arm64-v8a', policy='Enforcing', kernel='aarch64'):
        (ROOT / 'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            folder = Path(directory)
            (folder / 'ci').mkdir()
            shutil.copyfile(ROOT / 'ci/run-device-acceptance.sh', folder / 'ci/run-device-acceptance.sh')
            shutil.copyfile(ROOT / 'run-device-proof.sh', folder / 'run-device-proof.sh')
            adb = folder / 'adb'
            adb.write_text('#!' + sys.executable + '\n' + '''
import os, sys
args = sys.argv[1:]
if args[:2] == ['shell', 'getprop']:
    print({'ro.product.cpu.abi': os.environ['TP_TEST_ABI'],
           'ro.build.version.sdk': '30', 'ro.build.fingerprint': 'fixture'}.get(args[2], ''))
elif args[:2] == ['shell', 'uname']:
    print(os.environ['TP_TEST_KERNEL'])
elif args[:2] == ['shell', 'getenforce']:
    print(os.environ['TP_TEST_POLICY'])
elif args[0] == 'exec-out':
    print(os.environ['TP_TEST_REPORT'])
elif args[0] == 'logcat':
    print('fixture logcat')
else:
    print('fixture adb success')
''')
            adb.chmod(0o755)
            apk = folder / 'proof.apk'
            apk.write_bytes(b'host-fixture-not-an-apk')
            env = dict(os.environ, PATH=directory + ':' + os.environ['PATH'],
                       TP_TEST_REPORT=report, TP_TEST_ABI=abi, TP_TEST_POLICY=policy, TP_TEST_KERNEL=kernel)
            result = subprocess.run(['bash', str(folder / 'ci/run-device-acceptance.sh'), str(apk)],
                                    env=env, capture_output=True, text=True, timeout=10)
            evidence = folder / 'build/evidence/device-arm64'
            return result, (evidence / 'status.txt').read_text(), (evidence / 'logcat.log').read_text()

    def test_complete_native_report_can_pass_orchestration(self):
        report = '\n'.join(f'case={case} exit=0 expected=0' for case in
                           ['protected', 'execve', 'execvp', 'spawnp', 'raw', 'relative'])
        report += '\ncase=unregistered exit=64 expected=64\ncase=bad-arguments exit=65 expected=65'
        report += '\nE0/E1 candidate probes=PASS exit=0 (matrix review still required)'
        result, status, _ = self.run_proof(report)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('E0/E1=PASS (this ARM64 device run only', status)

    def test_success_marker_without_native_cases_stays_unverified(self):
        result, status, logcat = self.run_proof('E0/E1 candidate probes=PASS exit=0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('E0/E1=UNVERIFIED', status)
        self.assertIn('fixture logcat', logcat)

    def test_wrong_abi_stays_unverified_and_collects_logs(self):
        result, status, logcat = self.run_proof('E0/E1 candidate probes=PASS exit=0', abi='x86_64')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('E0/E1=UNVERIFIED', status)
        self.assertIn('fixture logcat', logcat)

    def test_permissive_guest_stays_unverified(self):
        result, status, logcat = self.run_proof('E0/E1 candidate probes=PASS exit=0', policy='Permissive')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('E0/E1=UNVERIFIED', status)
        self.assertIn('fixture logcat', logcat)

    def test_environment_guards_fail_closed_on_empty_or_pattern_values(self):
        for fields in [{'kernel': 'x86_64'}, {'kernel': ''}, {'abi': 'arm64*'},
                       {'abi': ''}, {'policy': '*'}, {'policy': ''}]:
            with self.subTest(fields=fields):
                result, status, logcat = self.run_proof('not device evidence', **fields)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('E0/E1=UNVERIFIED', status)
                self.assertIn('exit_code=1', status)
                self.assertIn('fixture logcat', logcat)


if __name__ == '__main__':
    unittest.main()
