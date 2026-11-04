"""Linux explicit-linker regression; this cannot supply Android E2 acceptance."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT.parent / 'shared/native'


class LinkerProof(unittest.TestCase):
    def test_compatible_dynamic_target_and_full_process_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-fPIE', '-pie',
                     '-Wl,-z,max-page-size=16384', '-I' + str(COMMON),
                     '-DTP_ELF_MACHINE=EM_X86_64',
                     '-DTP_SYSTEM_LINKER="/lib64/ld-linux-x86-64.so.2"']
            for name in ['target', 'launcher', 'driver']:
                sources = [str(ROOT / f'proof/native/e2-{name}.c')]
                if name == 'target':
                    # Force SIGWINCH to arrive between READY and waiting. A check-then-pause
                    # loop loses this wakeup; the target must use an atomic signal wait.
                    source = Path(sources[0]).read_text()
                    ready = 'puts("E2 PTY READY"); fflush(stdout);'
                    self.assertEqual(source.count(ready), 1)
                    delayed = folder / 'target-delayed.c'
                    delayed.write_text(source.replace(ready, ready + ' usleep(100000);'))
                    sources = [str(delayed)]
                if name != 'target':
                    sources.append(str(COMMON / 'tp_exec.c'))
                subprocess.run(['gcc', *flags, *sources, '-o', str(folder / name)], check=True)
            (folder / 'target').chmod(0o600)
            env = dict(os.environ, TP_E2_LAUNCHER=str(folder / 'launcher'), TP_E2_TARGET=str(folder / 'target'))
            result = subprocess.run([str(folder / 'driver')], cwd=folder, env=env,
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('E2 candidate probes=PASS failures=0; E3=NOT RUN', result.stdout)
            self.assertIn('e2case=static-reject exit=126 expected=126', result.stdout)
            self.assertIn('e2case=wrong-abi exit=126 expected=126', result.stdout)
            self.assertIn('e2case=pty-control exit=0 expected=0', result.stdout)
            self.assertIn('E2 args/env/cwd/pid/fd/stdin=PASS', result.stdout)
            self.assertIn('E2 stderr=preserved', result.stderr)


if __name__ == '__main__':
    unittest.main()
