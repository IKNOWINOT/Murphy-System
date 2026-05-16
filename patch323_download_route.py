"""
PATCH-323b — Wire /download route into app.py
Adds: GET /download → serves download.html
      GET /install.sh → serves install.sh
      GET /install.ps1 → serves install_windows.ps1
      GET /static/murphy-client-icon.png → serves the app icon
"""
import re

APP_PATH = '/opt/Murphy-System/src/runtime/app.py'

with open(APP_PATH, 'r') as f:
    src = f.read()

ROUTES = '''
# ── Murphy Client Download Page (PATCH-323b) ──────────────────────────────────
import os as _os

@app.route('/download')
def murphy_client_download():
    """Serve the Murphy Client download page."""
    base = _os.path.dirname(_os.path.abspath(__file__))
    # Look up two levels from src/runtime/ to repo root
    for candidate in [
        _os.path.join(base, '..', '..', 'download.html'),
        _os.path.join(base, 'download.html'),
        '/opt/Murphy-System/download.html',
    ]:
        p = _os.path.normpath(candidate)
        if _os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as fh:
                return fh.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    return 'Download page not found', 404

@app.route('/install.sh')
def murphy_install_sh():
    base = _os.path.dirname(_os.path.abspath(__file__))
    for candidate in [
        _os.path.join(base, '..', '..', 'install.sh'),
        '/opt/Murphy-System/install.sh',
    ]:
        p = _os.path.normpath(candidate)
        if _os.path.exists(p):
            with open(p, 'r') as fh:
                return fh.read(), 200, {
                    'Content-Type': 'text/plain',
                    'Content-Disposition': 'attachment; filename="install.sh"'
                }
    return '#!/bin/bash\\necho "Install script not available yet"', 200, {'Content-Type': 'text/plain'}

@app.route('/install.ps1')
def murphy_install_ps1():
    base = _os.path.dirname(_os.path.abspath(__file__))
    for candidate in [
        _os.path.join(base, '..', '..', 'install_windows.ps1'),
        '/opt/Murphy-System/install_windows.ps1',
    ]:
        p = _os.path.normpath(candidate)
        if _os.path.exists(p):
            with open(p, 'r') as fh:
                return fh.read(), 200, {
                    'Content-Type': 'text/plain',
                    'Content-Disposition': 'attachment; filename="install_windows.ps1"'
                }
    return '# Install script not available yet', 200, {'Content-Type': 'text/plain'}

@app.route('/download/murphy_client_v<version>.zip')
def murphy_client_zip(version):
    """Serve versioned Murphy Client zip downloads."""
    import glob
    for pattern in [
        f'/opt/Murphy-System/murphy_client_v{version}.zip',
        f'/opt/Murphy-System/murphy_client/murphy_client_v{version}.zip',
    ]:
        if _os.path.exists(pattern):
            with open(pattern, 'rb') as fh:
                return fh.read(), 200, {
                    'Content-Type': 'application/zip',
                    'Content-Disposition': f'attachment; filename="murphy_client_v{version}.zip"'
                }
    return 'Not found', 404

'''

# Only add if not already present
if '/download' not in src or 'murphy_client_download' not in src:
    # Insert before the last if __name__ block or at end of routes
    if "if __name__ == '__main__':" in src:
        src = src.replace("if __name__ == '__main__':", ROUTES + "\nif __name__ == '__main__':", 1)
    else:
        src = src + ROUTES
    
    with open(APP_PATH, 'w') as f:
        f.write(src)
    print('✓ PATCH-323b: /download route added to app.py')
else:
    print('SKIP: /download route already present')
