
#!/usr/bin/env python3
import os, json, argparse
from datetime import datetime, timezone
try:
    from PIL import ImageGrab
except Exception:
    ImageGrab=None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--id', required=True)
    ap.add_argument('--out', default='locators')
    ap.add_argument('--region', nargs=4, type=int, help='x y w h', required=True)
    a=ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    x,y,w,h = a.region
    if ImageGrab is None:
        print('[locator] PIL not available; cannot capture'); return
    img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
    png = os.path.join(a.out, f'{a.id}.png')
    img.save(png)
    meta = {'id': a.id, 'kind':'image', 'path': png, 'notes':'auto-captured', 'ts': datetime.now(timezone.utc).isoformat()}
    with open(os.path.join(a.out, f'{a.id}.json'), 'w', encoding='utf-8') as f: json.dump(meta, f, indent=2)
    print('[locator] saved', png)
if __name__=='__main__': main()
