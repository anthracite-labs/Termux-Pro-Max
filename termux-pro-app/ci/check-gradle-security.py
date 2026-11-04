#!/usr/bin/env python3
"""Exercise strict Gradle verification without modifying the shared dependency cache."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'v': 'https://schema.gradle.org/dependency-verification'}


def check():
    with tempfile.TemporaryDirectory(prefix='gradle-security-') as directory:
        project = Path(directory)
        (project / 'gradle').mkdir()
        for name in ['build.gradle', 'buildscript-gradle.lockfile', 'settings.gradle']:
            shutil.copyfile(ROOT / name, project / name)
        # Resolve only the production plugin classpath, without Android modules or SDK.
        settings = project / 'settings.gradle'
        settings.write_text(settings.read_text().split("rootProject.name", 1)[0])
        metadata = project / 'gradle/verification-metadata.xml'
        shutil.copyfile(ROOT / 'gradle/verification-metadata.xml', metadata)
        command = [str(ROOT / 'gradlew'), '--offline', '--no-daemon', '--dependency-verification',
                   'strict', '-p', str(project), 'help']
        positive = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if positive.returncode:
            raise RuntimeError(positive.stdout + positive.stderr)
        tree = ET.parse(metadata)
        artifact = tree.find(".//v:component[@group='com.android.tools.build'][@name='gradle']/v:artifact[@name='gradle-8.10.1.jar']/v:sha256", NS)
        if artifact is None:
            raise ValueError('production AGP checksum is missing')
        artifact.set('value', '0' * 64)
        ET.register_namespace('', NS['v'])
        tree.write(metadata, encoding='utf-8', xml_declaration=True)
        negative = subprocess.run(command, capture_output=True, text=True, timeout=180)
        output = negative.stdout + negative.stderr
        if negative.returncode == 0 or 'Dependency verification failed' not in output or 'gradle-8.10.1.jar' not in output:
            raise AssertionError('Gradle did not reject the incorrect AGP checksum:\n' + output)
        print('PASS_HOST: locked production plugin classpath verifies; incorrect SHA-256 is rejected.')


if __name__ == '__main__':
    check()
