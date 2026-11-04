"""Execute the Android fixture's actual TTY-report prologue on a Linux PTY."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceTty(unittest.TestCase):
    def probe(self, log):
        source = (ROOT / 'app/src/androidTest/java/com/anthracitelabs/termuxpro/TerminalAcceptance.java').read_text()
        start = source.index('String command = ')
        block = source[start:source.index('\n        main(() -> { shell.write(command);', start)]
        tokens = re.findall(r'"(?:\\.|[^"\\])*"|\blog\b', block)
        command = ''.join(str(log) if token == 'log' else json.loads(token) for token in tokens)
        # Only the TTY report is under test; later commands require Android's /system/bin.
        return command[:command.index('bash --noprofile')] + "printf 'done\\n'; } > '" + str(log) + "'\n"

    def test_tty_is_checked_before_redirect_and_pipes_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'report'
            master, slave = os.openpty()
            try:
                subprocess.run(['bash', '-c', self.probe(log)], stdin=slave, stdout=slave,
                               stderr=slave, check=True, timeout=10)
            finally:
                os.close(slave); os.close(master)
            self.assertIn('tty=0\n', log.read_text())
            subprocess.run(['bash', '-c', self.probe(log)], capture_output=True, check=True, timeout=10)
            self.assertIn('tty=1\n', log.read_text())
