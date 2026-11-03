"""Linux regression checks for the probe; never evidence of Android acceptance."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExecutionProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.launcher = cls.base / 'libtp-launcher.so'
        cls.driver = cls.base / 'libtp-driver.so'
        for source, output in [('probe.c', cls.launcher), ('driver.c', cls.driver)]:
            subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fPIE', '-pie', str(ROOT / 'proof/native' / source),
                            '-o', str(output)], check=True)
        cls.prefix = cls.base / 'usr'
        (cls.prefix / 'bin').mkdir(parents=True)
        (cls.prefix / 'bin/gh').symlink_to(cls.launcher)
        (cls.prefix / 'bin/unregistered').symlink_to(cls.launcher)
        cls.env = dict(os.environ, TP_PROOF_PREFIX=str(cls.prefix),
                       TP_PROOF_LAUNCHER=str(cls.launcher),
                       PATH=str(cls.prefix / 'bin') + ':/usr/bin:/bin')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_driver_exercises_all_launch_variants(self):
        result = subprocess.run([str(self.driver)], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for case in ['protected', 'execve', 'execvp', 'spawnp', 'raw', 'relative']:
            self.assertIn(f'case={case} exit=0', result.stdout)
        self.assertEqual(result.stdout.count('identity=gh'), 5)
        self.assertIn('case=unregistered exit=64 expected=64', result.stdout)
        self.assertIn('case=bad-arguments exit=65 expected=65', result.stdout)

    def test_argv0_alone_cannot_claim_a_registered_command(self):
        args = ['gh', '', 'a b', '--', '日本語', "'quoted'"]
        result = subprocess.run(args, executable=str(self.launcher), env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('identity=protected', result.stdout)

    def test_unregistered_symlink_is_rejected_even_with_gh_argv0(self):
        alias = self.prefix / 'bin/other'
        alias.symlink_to(self.launcher)
        result = subprocess.run(['gh', '', 'a b', '--', '日本語', "'quoted'"],
                                executable=str(alias), env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 64, result.stdout + result.stderr)

    def test_argument_changes_fail_the_probe(self):
        result = subprocess.run([str(self.launcher), 'lost empty argument'],
                                env=self.env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 65)

    def test_resolving_away_the_command_name_must_fail_identity_expectation(self):
        env = dict(self.env, TP_PROOF_EXPECT_IDENTITY='gh')
        result = subprocess.run([str(self.launcher), '', 'a b', '--', '日本語', "'quoted'"],
                                env=env, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 66)


if __name__ == '__main__':
    unittest.main()
