"""Linux regression checks for the probe; never evidence of Android acceptance."""
import os
from pathlib import Path
import signal
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

    def test_aliased_directories_preserve_command_identity(self):
        alias = self.base / 'aliased-parent'
        alias.symlink_to(self.base, target_is_directory=True)
        env = dict(self.env, TP_PROOF_LAUNCHER=str(alias / self.launcher.name),
                   TP_PROOF_PREFIX=str(alias / 'usr'), PATH=str(alias / 'usr/bin'))
        result = subprocess.run([str(self.driver)], env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('identity=gh'), 5)

    def run_hung_probe(self, terminate=False):
        source = self.base / 'hung.c'
        source.write_text('#include <stdio.h>\n#include <unistd.h>\n'
                          'int main(void) { printf("hung_pid=%ld\\n", (long)getpid());'
                          'fflush(stdout); for (;;) pause(); }\n')
        hung = self.base / 'hung'
        subprocess.run(['gcc', str(source), '-o', str(hung)], check=True)
        env = dict(self.env, TP_PROOF_LAUNCHER=str(hung))
        process = subprocess.Popen([str(self.driver)], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, start_new_session=True)
        child_pid = None
        try:
            line = process.stdout.readline()
            self.assertTrue(line.startswith('hung_pid='), line)
            child_pid = int(line.split('=')[1])
            if terminate:
                process.terminate()
            try:
                output, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self.fail('driver failed to bound/reap a hung probe')
            self.assertEqual(process.returncode, 143 if terminate else 124, output)
            self.assertIn('interrupted=15' if terminate else 'timeout=1', output)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            for pid in [process.pid, child_pid]:
                if pid is not None:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            process.communicate()

    def test_hung_probe_is_timed_out_killed_and_reaped(self):
        self.run_hung_probe()

    def test_terminating_driver_kills_and_reaps_active_probe(self):
        self.run_hung_probe(terminate=True)

    def test_run_directories_preserve_packages_and_other_runs(self):
        java_bin = Path(os.environ['JAVA_HOME']) / 'bin' if 'JAVA_HOME' in os.environ else Path('')
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([str(java_bin / 'javac'), '-d', directory,
                            str(ROOT / 'proof/src/main/java/com/anthracitelabs/termuxpro/ProofFiles.java'),
                            str(ROOT / 'tests/ProofFilesTest.java')], check=True)
            subprocess.run([str(java_bin / 'java'), '-cp', directory,
                            'com.anthracitelabs.termuxpro.ProofFilesTest', directory],
                           check=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
