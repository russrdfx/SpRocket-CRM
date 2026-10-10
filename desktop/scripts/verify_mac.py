"""Reject Mac ZIPs with invalid app signature integrity before distribution."""
import json
import subprocess
import tempfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
version = json.loads((root/'package.json').read_text())['version']
archive = root/'dist'/f'SpRocket-CRM-{version}-arm64.zip'
with tempfile.TemporaryDirectory() as folder:
    subprocess.run(['ditto','-x','-k',str(archive),folder],check=True)
    bundle = Path(folder)/'SpRocket CRM.app'
    subprocess.run(['codesign','--verify','--deep','--strict','--verbose=2',str(bundle)],check=True)
print('Freshly extracted Mac application passes strict signature integrity verification.')
