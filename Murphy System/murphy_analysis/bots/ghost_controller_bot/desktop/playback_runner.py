
#!/usr/bin/env python3
import sys, json, time, argparse
def have(name): 
    try: __import__(name); return True
    except Exception: return False
def focus_app(app): print(f'[focus_app] -> {app}')
def type_text(txt):
    if have('pyautogui'):
        import pyautogui; pyautogui.typewrite(txt, interval=0.02)
    else: print(f'[type] {txt[:60]}...')
def click(x=None,y=None,image=None,confidence=0.8):
    if have('pyautogui'):
        import pyautogui
        if image:
            try:
                p=pyautogui.locateCenterOnScreen(image, confidence=confidence)
                if p: pyautogui.click(p); return True
                print('[click-image] not found', image); return False
            except Exception as e:
                print('[click-image] error', e); return False
        else:
            pyautogui.click(x=x or 0,y=y or 0); return True
    else:
        print(f'[click] ({x},{y}) image={image} (pyautogui missing)'); return False
def wait(s=0.5): time.sleep(s)
def assert_window_title(substr):
    try:
        import pygetwindow as gw
        w=gw.getActiveWindow(); title = w.title if w else ''
        ok = (substr or '').lower() in (title or '').lower()
        print(f'[assert_window] want~="{substr}" got="{title}" -> {"PASS" if ok else "FAIL"}'); return ok
    except Exception as e:
        print('[assert_window] unavailable', e); return False
def assert_ocr_contains(substr, region=None):
    try:
        import pytesseract, PIL.ImageGrab as IG
        box = tuple(region) if region and len(region)==4 else None
        img = IG.grab(bbox=box) if box else IG.grab()
        txt = pytesseract.image_to_string(img) or ''
        ok = (substr or '').lower() in txt.lower()
        print(f'[assert_ocr] want~="{substr}" -> {"PASS" if ok else "FAIL"}'); return ok
    except Exception as e:
        print('[assert_ocr] unavailable', e); return False
def post_validation(url, payload):
    try:
        import requests; requests.post(url, json=payload, timeout=2)
    except Exception as e:
        print('[validate post] error', e)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('spec', nargs='?')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--validate-url', default='http://127.0.0.1:8775/validate')
    a=ap.parse_args()
    obj = json.load(open(a.spec,'r',encoding='utf-8')) if a.spec else json.load(sys.stdin)
    steps = obj.get('steps',[])
    if not a.force: print('[info] Dry-run default. Use --force to click/type.')
    for s in steps:
        act=s.get('action'); args=s.get('args',{}); ok=True
        if act=='focus_app': focus_app(args.get('app',''))
        elif act=='type' and not a.dry_run and a.force: type_text(args.get('text',''))
        elif act=='click' and not a.dry_run and a.force: ok=click(args.get('x'), args.get('y'), args.get('image'), args.get('confidence',0.8))
        elif act=='wait': wait(args.get('seconds',0.5))
        elif act=='assert_window': ok=assert_window_title(args.get('contains',''))
        elif act=='assert_ocr': ok=assert_ocr_contains(args.get('contains',''), args.get('region'))
        else: print(f'[skip] {act}')
        post_validation(a.validate_url, {'microtask_id': s.get('id','step'), 'passed':bool(ok), 'details':act})
    print('[done]')
if __name__=='__main__': main()
