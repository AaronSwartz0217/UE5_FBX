"""Build a source-only UE plugin archive; exclude caches and engine test projects."""
import ast
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
plugin = root / 'SmartFbxMaterials'
json.loads((plugin / 'SmartFbxMaterials.uplugin').read_text(encoding='utf-8'))
for path in (plugin / 'Content/Python').glob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
archive = root / 'SmartFbxMaterials-1.0.0-UE5.5plus.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
    for path in sorted(plugin.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            output.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as check:
    assert check.testzip() is None
    print('\n'.join(check.namelist()))
print('SHA256', hashlib.sha256(archive.read_bytes()).hexdigest())
