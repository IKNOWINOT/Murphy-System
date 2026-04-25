#!/opt/Murphy-System/venv/bin/python3
"""
Murphy Autonomous Integration Batch Builder — PATCH-083b
Runs directly on server, builds all priority integrations in order,
commits each one individually as it completes. No HTTP timeouts.

Usage: python3 /opt/Murphy-System/scripts/batch_build_integrations.py
"""
import sys, os, time, json, subprocess
sys.path.insert(0, '/opt/Murphy-System')
sys.path.insert(0, '/opt/Murphy-System/src')

# Load env
for path in ['/etc/murphy-production/environment', '/etc/murphy-production/secrets.env']:
    try:
        for line in open(path).readlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

from src.integration_builder import (
    PRIORITY_INTEGRATION_TARGETS, build_integration, _already_built, _load_build_log
)

DEPLOY_DIR = '/opt/Murphy-System'

def git_commit(service, score):
    try:
        subprocess.run(['git', '-C', DEPLOY_DIR, 'add', '-A'], check=True, capture_output=True)
        msg = f"AUTO-INTEG: {service} connector ({score:.1f}/15) — autonomous build"
        subprocess.run(['git', '-C', DEPLOY_DIR, 'commit', '-m', msg], 
                      check=True, capture_output=True)
        subprocess.run(['git', '-C', DEPLOY_DIR, 'push', 'origin', 'main'],
                      capture_output=True)  # non-fatal if push fails
        print(f"    ✅ Committed: {msg}")
    except Exception as e:
        print(f"    ⚠️  Commit failed: {e}")

def main():
    log = _load_build_log()
    attempted = {e['service'] for e in log}
    
    to_build = [
        t for t in PRIORITY_INTEGRATION_TARGETS
        if t['service'] not in attempted and not _already_built(t['service'])
    ]
    
    print(f"\n{'='*60}")
    print(f"  Murphy Autonomous Integration Builder — PATCH-083b")
    print(f"  {len(to_build)} integrations queued")
    print(f"{'='*60}\n")
    
    succeeded = 0
    failed = 0
    scores = []
    
    for i, target in enumerate(to_build):
        service = target['service']
        cat = target['category']
        desc = target['description']
        
        print(f"[{i+1}/{len(to_build)}] Building {service} ({cat})...")
        t0 = time.time()
        
        try:
            result = build_integration(service, cat, desc, search_docs=False)
            elapsed = round(time.time() - t0, 1)
            
            if result.get('ok'):
                score = result.get('quality_score', 0)
                grade = result.get('quality_grade', '?')
                methods = result.get('methods', [])
                scores.append(score)
                succeeded += 1
                print(f"    ✅ {service}: {score:.1f}/15 ({grade}) — {len(methods)} methods — {elapsed}s")
                if result.get('quality_strengths'):
                    print(f"       strengths: {result['quality_strengths'][:2]}")
                # Commit immediately
                git_commit(service, score)
            else:
                failed += 1
                print(f"    ❌ {service}: {result.get('error','?')[:80]}")
        except Exception as e:
            failed += 1
            print(f"    ❌ {service}: Exception: {e}")
        
        # Rate limit: 3s between builds to avoid DeepInfra throttle
        if i < len(to_build) - 1:
            time.sleep(3)
    
    avg_score = sum(scores)/len(scores) if scores else 0
    print(f"\n{'='*60}")
    print(f"  Done: {succeeded} built, {failed} failed")
    print(f"  Average quality score: {avg_score:.1f}/15")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
