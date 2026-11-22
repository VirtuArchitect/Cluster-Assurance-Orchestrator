"""Check canonical release metadata without importing application dependencies."""
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def check():
 release=json.loads((ROOT/'backend/app/release.json').read_text())
 assert re.fullmatch(r'\d+\.\d+\.\d+(?:-rc\.\d+)?',release['version']), 'Invalid semantic version'
 assert release['python_version']==release['version'].replace('-rc.','rc')
 for file in ['frontend/package.json','frontend/package-lock.json']:
  data=json.loads((ROOT/file).read_text());assert data['version']==release['version'],file
  if 'packages' in data:assert data['packages']['']['version']==release['version']
 assert release['production_approved'] is False, 'Acceptance must remain separate from source metadata'
 print('Release metadata consistent:',release['version'])
if __name__=='__main__':check()
