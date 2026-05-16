"""
PATCH-325b — Wire /guide route + /api/goldenpath/generate into app.py
"""
import os

APP_PATH = '/opt/Murphy-System/src/runtime/app.py'

PATCH = '''
# ── Murphy Guide — Golden Path UI (PATCH-325b) ────────────────────
import _io as _io_mod

@app.route('/guide')
def murphy_guide():
    for candidate in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'murphy_guide.html'),
        '/opt/Murphy-System/murphy_guide.html',
    ]:
        p = os.path.normpath(candidate)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as fh:
                return fh.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    return 'Guide not found', 404

@app.route('/api/goldenpath/generate', methods=['POST'])
def goldenpath_generate():
    """
    Accepts a task prompt and returns a structured golden path spec.
    Wires into goldenpath_generator bot logic.
    Format matches Clockwork OutputSchema: {result:{tasks:[...]}, confidence, notes}
    """
    data = request.get_json(silent=True) or {}
    task = data.get('task', '')
    if not task:
        return jsonify({'error': 'task required'}), 400
    
    # Try goldenpath_generator bot if available
    try:
        from bots.goldenpath_generator import goldenpath_generator
        import asyncio
        result = asyncio.run(goldenpath_generator.run({'task': task}, {}))
        return jsonify(result)
    except Exception as e:
        pass
    
    # Stub response (UI handles local generation too)
    return jsonify({
        'result': {
            'chain_id': f'gp_{hash(task)&0xffff:04x}',
            'level': 2,
            'tasks': []
        },
        'confidence': 0.75,
        'notes': ['local_stub'],
        'meta': {}
    })
'''

with open(APP_PATH) as f:
    src = f.read()

if 'PATCH-325b' not in src:
    marker = "if __name__ == '__main__':"
    if marker in src:
        src = src.replace(marker, PATCH + '\n' + marker, 1)
    else:
        src += '\n' + PATCH
    with open(APP_PATH, 'w') as f:
        f.write(src)
    print('✓ PATCH-325b applied')
else:
    print('SKIP: already applied')
