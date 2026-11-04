"""Host checks of explicit Android network policy and locked Gradle inputs."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ANDROID = '{http://schemas.android.com/apk/res/android}'


class BuildSecurity(unittest.TestCase):
    def test_both_applications_explicitly_reject_cleartext(self):
        for module in ['app', 'proof']:
            with self.subTest(module=module):
                application = ET.parse(ROOT / module / 'src/main/AndroidManifest.xml').getroot().find('application')
                self.assertEqual(application.get(ANDROID + 'usesCleartextTraffic'), 'false')

    def test_all_projects_lock_dependencies_and_verify_artifacts(self):
        build = (ROOT / 'build.gradle').read_text()
        self.assertIn('lockAllConfigurations()', build)
        self.assertIn('activateDependencyLocking()', build)
        for module in ['app', 'proof', 'vendor/terminal-view', 'vendor/terminal-emulator']:
            with self.subTest(module=module):
                lock = (ROOT / module / 'gradle.lockfile').read_text()
                self.assertIn('Gradle generated file for dependency locking', lock)
        ns = {'v': 'https://schema.gradle.org/dependency-verification'}
        verification = ET.parse(ROOT / 'gradle/verification-metadata.xml').getroot()
        self.assertEqual(verification.find('v:configuration/v:verify-metadata', ns).text, 'true')
        self.assertFalse(verification.findall('.//v:trusted-artifacts', ns))
        artifacts = verification.findall('.//v:artifact', ns)
        self.assertTrue(artifacts)
        for artifact in artifacts:
            digests = artifact.findall('v:sha256', ns)
            self.assertEqual(len(digests), 1, artifact.get('name'))
            self.assertRegex(digests[0].get('value'), r'^[0-9a-f]{64}$')
