"""Exercise production dispatcher and PTY code on Linux; Android remains NOT RUN."""
import ctypes
import errno
import os
from pathlib import Path
import select
import shutil
import signal
import struct
import subprocess
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class Runtime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        cls.prefix = cls.work / 'usr'
        for name in ['bin', 'libexec/tp-real', 'var/lib/termux-pro/commands']:
            (cls.prefix / name).mkdir(parents=True, exist_ok=True)
        cls.launcher = cls.work / 'launcher'
        flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-fPIE', '-pie',
                 '-Wl,-z,max-page-size=16384', '-DTP_ELF_MACHINE=EM_X86_64',
                 '-DTP_SYSTEM_LINKER="/lib64/ld-linux-x86-64.so.2"',
                 '-DTP_PREFIX="' + str(cls.prefix) + '"', '-I' + str(ROOT.parent / 'shared/native')]
        subprocess.run(['gcc', *flags, str(ROOT / 'app/native/launcher.c'),
                        str(ROOT.parent / 'shared/native/tp_exec.c'), '-o', str(cls.launcher)], check=True)
        cls.flags = flags
        target = cls.work / 'target.c'
        target.write_text('#include <stdio.h>\nint main(int argc, char **argv) { for(int i=1;i<argc;i++) printf("[%s]",argv[i]); puts(""); return 7; }\n')
        cls.target = cls.prefix / 'libexec/tp-real/fixture'
        subprocess.run(['gcc', *flags, str(target), '-o', str(cls.target)], check=True)
        cls.target.chmod(0o600)
        cls.entry = cls.prefix / 'bin/fixture'; cls.entry.symlink_to(cls.launcher)
        cls.registry = cls.prefix / 'var/lib/termux-pro/commands/fixture'
        cls.registry.write_text('libexec/tp-real/fixture\n')
        library = cls.work / 'pty.so'
        subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fPIC', '-shared',
                        str(ROOT / 'app/native/pty.c'), '-o', str(library)], check=True)
        cls.pty = ctypes.CDLL(str(library), use_errno=True)
        cls.pty.tp_pty_start.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_int),
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        cls.pty.tp_pty_start.restype = ctypes.c_int
        cls.pty.tp_pty_resize.argtypes = [ctypes.c_int] * 5
        cls.pty.tp_pty_resize.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_managed_identity_is_independent_of_forged_argv0_and_target_is_dynamic(self):
        for executable, args in [(self.entry, ['forged-git', '', 'a b', '日本語']),
                                  (self.launcher, ['forged-git', '--tp-command', 'fixture', '', 'a b', '日本語'])]:
            result = subprocess.run(args, executable=executable, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual(result.stdout, '[][a b][日本語]\n')
        alias = self.prefix / 'bin/unregistered'; alias.symlink_to(self.launcher)
        result = subprocess.run(['fixture'], executable=alias, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 64)
        self.assertEqual(subprocess.run([str(self.launcher), '--tp-command', '../fixture'], capture_output=True).returncode, 64)
        original = self.target.read_bytes()
        try:
            self.target.write_text('#!/system/bin/sh\nexit 0\n')
            self.assertEqual(subprocess.run([str(self.entry)], capture_output=True).returncode, 126)
        finally:
            self.target.write_bytes(original)

    def test_compiled_prefix_alias_uses_canonical_managed_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); real = folder / 'real-files'; real.mkdir()
            alias = folder / 'alias-files'; alias.symlink_to(real, target_is_directory=True)
            prefix = real / 'usr'
            for name in ['bin', 'libexec/tp-real', 'var/lib/termux-pro/commands']:
                (prefix / name).mkdir(parents=True)
            target = prefix / 'libexec/tp-real/fixture'; target.write_bytes(self.target.read_bytes()); target.chmod(0o600)
            (prefix / 'var/lib/termux-pro/commands/fixture').write_text('libexec/tp-real/fixture\n')
            launcher = folder / 'launcher'
            flags = [x for x in self.flags if not x.startswith('-DTP_PREFIX=')]
            flags.append('-DTP_PREFIX="' + str(alias / 'usr') + '"')
            subprocess.run(['gcc', *flags, str(ROOT / 'app/native/launcher.c'),
                            str(ROOT.parent / 'shared/native/tp_exec.c'), '-o', str(launcher)], check=True)
            (prefix / 'bin/fixture').symlink_to(launcher)
            for args in [[str(alias / 'usr/bin/fixture'), 'value'], [str(launcher), '--tp-command', 'fixture', 'value']]:
                result = subprocess.run(args, text=True, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual(result.stdout, '[value]\n')
            registry = prefix / 'var/lib/termux-pro/commands/fixture'
            saved = folder / 'forged-registry'; saved.write_text(registry.read_text())
            registry.unlink(); registry.symlink_to(saved)
            self.assertEqual(subprocess.run([str(launcher), '--tp-command', 'fixture'], capture_output=True).returncode, 64)
            registry.unlink(); registry.write_text(saved.read_text())
            moved = real / 'moved-usr'; prefix.rename(moved); prefix.symlink_to(moved)
            self.assertEqual(subprocess.run([str(launcher), '--tp-command', 'fixture'], capture_output=True).returncode, 64)

    def launch(self, command, args, cwd=None):
        array = (ctypes.c_char_p * (len(args) + 1))(*[a.encode() for a in args], None)
        variables = (ctypes.c_char_p * 4)(b'PATH=/usr/bin:/bin', b'TERM=xterm-256color', b'PS1=TP> ', None)
        pid = ctypes.c_int()
        fd = self.pty.tp_pty_start(command.encode(), str(cwd or self.work).encode(), array, variables,
                                   ctypes.byref(pid), 24, 80, 8, 16)
        return fd, pid.value

    def read_until(self, fd, marker):
        output = b''; end = time.monotonic() + 5
        while time.monotonic() < end:
            if select.select([fd], [], [], max(0, end - time.monotonic()))[0]:
                try:
                    data = os.read(fd, 4096)
                except OSError as error:
                    if error.errno == errno.EIO: break
                    raise
                if not data: break
                output += data
                if marker in output: return output
        self.fail(f'PTY did not produce {marker!r}: {output!r}')

    def test_real_controlling_pty_resize_ctrl_c_and_exit(self):
        fd, pid = self.launch('/bin/bash', ['/bin/bash', '--noprofile', '--norc', '-i'])
        self.assertGreaterEqual(fd, 0, os.strerror(ctypes.get_errno()))
        try:
            os.write(fd, b"printf 'PTY-READY\\n'; stty size\n")
            output = self.read_until(fd, b'24 80')
            self.assertNotIn(b'no job control', output)
            self.assertEqual(self.pty.tp_pty_resize(fd, 37, 103, 8, 16), 0)
            os.write(fd, b"stty size; sleep 30\n")
            self.read_until(fd, b'37 103')
            # stty can print before sleep becomes the foreground process.
            end = time.monotonic() + 5
            while time.monotonic() < end:
                foreground = os.tcgetpgrp(fd)
                comm = Path(f'/proc/{foreground}/comm')
                try:
                    name = comm.read_text().strip()
                except FileNotFoundError:
                    # A transient foreground group (stty) can exit before this read.
                    name = ''
                if foreground != pid and name == 'sleep': break
                time.sleep(0.01)
            else: self.fail('sleep never acquired the controlling PTY')
            os.write(fd, b'\x03')
            self.read_until(fd, b'TP> ')
            os.write(fd, b"printf 'INTERRUPTED=%s\\n' \"$?\"; exit 9\n")
            self.read_until(fd, b'INTERRUPTED=130')
            end = time.monotonic() + 5
            while time.monotonic() < end:
                found, status = os.waitpid(pid, os.WNOHANG)
                if found:
                    self.assertEqual(os.waitstatus_to_exitcode(status), 9); pid = -1; break
                time.sleep(0.01)
            self.assertEqual(pid, -1, 'shell was not reaped in time')
        finally:
            if pid > 0:
                os.kill(pid, signal.SIGKILL); os.waitpid(pid, 0)
            os.close(fd)

    def test_disappeared_foreground_process_is_retried_before_ctrl_c(self):
        original = Path.read_text
        disappeared = False
        def read_comm(path, *args, **kwargs):
            nonlocal disappeared
            if str(path).startswith('/proc/') and not disappeared:
                disappeared = True
                raise FileNotFoundError('foreground process exited before proc read')
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, 'read_text', read_comm):
            self.test_real_controlling_pty_resize_ctrl_c_and_exit()
        self.assertTrue(disappeared)

    def test_startup_errors_are_reported_and_reaped(self):
        fd, _ = self.launch('/does/not/exist', ['/does/not/exist'])
        self.assertEqual(fd, -1); self.assertEqual(ctypes.get_errno(), errno.ENOENT)
        fd, _ = self.launch('/bin/bash', ['/bin/bash'], cwd=self.work / 'missing')
        self.assertEqual(fd, -1); self.assertEqual(ctypes.get_errno(), errno.ENOENT)
