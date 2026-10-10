"""Build on the destination OS/architecture with PyInstaller installed."""
from pathlib import Path
import os
import subprocess
import sys
root = Path(__file__).resolve().parents[2]
desktop = root / 'desktop'
os.environ.setdefault('PYINSTALLER_CONFIG_DIR', str(desktop/'build'/'cache'))
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
    '--name', 'sprocket-server', '--distpath', str(desktop/'backend'),
    '--workpath', str(desktop/'build'), '--specpath', str(desktop/'build'),
    '--collect-all', 'jwt', '--collect-all', 'cryptography',
    '--add-data', str(root/'web')+':web', str(root/'server.py')], check=True)
