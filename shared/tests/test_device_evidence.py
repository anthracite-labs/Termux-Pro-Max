import hashlib
import json
from pathlib import Path
import re
import unittest
import zipfile

EVIDENCE = Path(__file__).resolve().parents[2] / 'docs/evidence/oppo-cph2819-api36'


class DeviceEvidence(unittest.TestCase):
    def test_supplied_artifact_and_scoped_results_are_intact(self):
        for line in (EVIDENCE / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), digest)
        record = json.loads((EVIDENCE / 'record.json').read_text())
        source = record['source_provenance']
        self.assertEqual(hashlib.sha256((EVIDENCE / 'proof-debug.apk').read_bytes()).hexdigest(), source['apk_sha256'])
        self.assertEqual(source['proof_apk_source_revision'], 'c54afeecf57b5863088ae9586f01c85a3f9232ee')
        self.assertFalse(source['cryptographic_binding_of_log_to_apk'])
        log = (EVIDENCE / 'device-proof.redacted.log').read_text()
        expected = {'protected': 0, 'execve': 0, 'execvp': 0, 'spawnp': 0,
                    'raw': 0, 'relative': 0, 'unregistered': 64, 'bad-arguments': 65}
        cases = re.findall(r'^case=(\S+) exit=(\d+) expected=(\d+)$', log, re.M)
        self.assertEqual(len(cases), 8)
        self.assertEqual({name: int(code) for name, code, _ in cases}, expected)
        self.assertTrue(all(code == wanted for _, code, wanted in cases))
        self.assertEqual(log.count('argv0_hex=666f726765642d676974'), 8)
        self.assertEqual(record['device']['page_size_bytes'], 4096)
        for gate in ['E0', 'E1']:
            self.assertEqual(record['gate_results'][gate]['status'], 'PASS_DEVICE_SPECIFIC_FIXTURE')
        for gate in ['E2', 'E3']:
            self.assertEqual(record['gate_results'][gate]['status'], 'NOT_RUN')
        with zipfile.ZipFile(EVIDENCE / 'proof-debug.apk') as apk:
            self.assertIsNone(apk.testzip())
            for name, digest in source['native_sha256'].items():
                self.assertEqual(hashlib.sha256(apk.read(name)).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
