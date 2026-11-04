"""Bind only an explicit builder-produced bootstrap into the signed APK assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

source, output = map(Path, sys.argv[1:])
root = Path(__file__).resolve().parents[2]
bootstrap = source / 'bootstrap.zip'
expected = (source / 'bootstrap.sha256').read_text().split()[0]
actual = hashlib.sha256(bootstrap.read_bytes()).hexdigest()
if expected != actual:
    raise SystemExit('Builder bootstrap checksum mismatch; rebuild before APK assembly')
revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
source_revision = source / 'source-revision.txt'
if source_revision.exists() and source_revision.read_text().strip() != revision:
    raise SystemExit('Builder artifact source revision does not match APK checkout')
output.mkdir(parents=True, exist_ok=True)
shutil.copyfile(bootstrap, output / 'bootstrap.zip')
(output / 'bootstrap.sha256').write_text(actual + '\n')
shutil.copyfile(root / 'shared/target.json', output / 'target.json')
dirty = bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True))
inputs = hashlib.sha256()
for base in [root / 'termux-pro-app/app', root / 'termux-pro-app/vendor', root / 'shared/native']:
    for path in sorted(base.rglob('*')):
        if path.is_file() and not any(part in {'build', '__pycache__'} for part in path.relative_to(base).parts):
            inputs.update(path.relative_to(root).as_posix().encode() + b'\0' + hashlib.sha256(path.read_bytes()).digest())
(output / 'build.json').write_text(json.dumps({'source_revision': revision + ('+dirty' if dirty else ''),
                                             'source_inputs_sha256': inputs.hexdigest(),
                                             'bootstrap_sha256': actual, 'android_runtime': 'NOT RUN'}) + '\n')

notices = output / 'notices'
notices.mkdir(exist_ok=True)
for name in ['LICENSE-APACHE-2.0.txt', 'UPSTREAM-LICENSE.md', 'README.md']:
    shutil.copyfile(root / 'termux-pro-app/vendor' / name, notices / name)
