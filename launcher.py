#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒體啟動器 - 本機媒體瀏覽與開啟工具
雙擊 啟動.bat 即可使用
"""
import http.server, json, os, subprocess, urllib.parse
import hashlib, threading, webbrowser, time, sys, socket, secrets
import urllib.request
from pathlib import Path

PORT     = 8765
APP_NAME = "MediaLauncher"

# ── Runtime paths ────────────────────────────────────────────────────
def app_dir() -> Path:
    """Installation directory (read-only when frozen in Program Files)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def data_dir() -> Path:
    """User-writable data directory.
    frozen exe → %APPDATA%\\MediaLauncher
    dev mode   → same folder as launcher.py
    """
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA')
        return Path(base) / APP_NAME if base else Path.home() / APP_NAME
    return app_dir()

SCRIPT    = app_dir()    # kept for any internal references that may still use it
DATA_DIR  = data_dir()
THUMB_DIR = DATA_DIR / ".thumbs"
CONFIG_F  = DATA_DIR / "config.json"
TASKS_F   = DATA_DIR / "tasks.json"

def _bundled_dir() -> Path:
    """Directory where PyInstaller places bundled datas.
    PyInstaller 6.x one-folder: sys._MEIPASS == _internal/ (not exe root).
    Dev mode: same as app_dir().
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return app_dir()

def _init_data_dir():
    """Create DATA_DIR and seed default config/tasks if missing (frozen mode)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    if getattr(sys, 'frozen', False):
        for fname in ('config.json', 'tasks.json'):
            dst = DATA_DIR / fname
            if not dst.exists():
                src = _bundled_dir() / fname   # PyInstaller 6.x: files land in _internal/
                if src.exists():
                    dst.write_bytes(src.read_bytes())

def find_ffmpeg() -> str:
    """Return path to ffmpeg: bundled tools/ffmpeg.exe first, then PATH."""
    bundled = _bundled_dir() / "tools" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"

def port_in_use(port: int) -> bool:
    """True if something is already listening on localhost:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('localhost', port)) == 0

FFMPEG_BIN = find_ffmpeg()

VIDEO_EXT = {'.mp4','.mkv','.avi','.mov','.webm','.m4v','.wmv','.flv','.ts','.mts','.mpg','.mpeg'}
AUDIO_EXT = {'.mp3','.wav','.flac','.aac','.ogg','.wma','.m4a','.opus','.aiff'}
IMAGE_EXT = {'.jpg','.jpeg','.png','.gif','.bmp','.webp','.tiff','.tif','.heic','.avif','.svg'}
PDF_EXT   = {'.pdf'}
PPT_EXT   = {'.ppt','.pptx'}
DOC_EXT   = {'.doc','.docx','.xls','.xlsx','.html','.htm','.txt','.csv','.rtf'}
ALL_EXT   = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT | PDF_EXT | PPT_EXT | DOC_EXT

IMAGE_MIME = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png',
              '.gif':'image/gif','.bmp':'image/bmp','.webp':'image/webp',
              '.svg':'image/svg+xml','.tiff':'image/tiff','.tif':'image/tiff',
              '.heic':'image/heic','.avif':'image/avif'}
MEDIA_MIME = {
    '.mp4':'video/mp4','.webm':'video/webm','.mov':'video/quicktime','.m4v':'video/mp4',
    '.mp3':'audio/mpeg','.wav':'audio/wav','.flac':'audio/flac','.aac':'audio/aac',
    '.ogg':'audio/ogg','.m4a':'audio/mp4','.opus':'audio/ogg',
    '.pdf':'application/pdf',
    **IMAGE_MIME
}

# ── Config ──────────────────────────────────────────────────────────
def load_cfg():
    cfg = None
    if CONFIG_F.exists():
        try: cfg = json.loads(CONFIG_F.read_text('utf-8-sig'))
        except: pass
    is_new = cfg is None
    if is_new:
        defaults = [str(Path.home()/d) for d in ('Desktop','Videos','Documents','Downloads')]
        cfg = {'dirs': [d for d in defaults if Path(d).is_dir()], 'recursive': False}
    cfg, migrated = migrate_cards_cfg(cfg)
    if is_new or migrated:
        try: save_cfg(cfg)
        except: pass
    return cfg

def save_cfg(cfg):
    CONFIG_F.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')

# ── Tasks ────────────────────────────────────────────────────────────
def load_tasks():
    if TASKS_F.exists():
        try: return json.loads(TASKS_F.read_text('utf-8-sig'))
        except: pass
    return {'activeTaskId': None, 'tasks': []}

def save_tasks(data):
    tmp = TASKS_F.with_suffix('.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
        tmp.replace(TASKS_F)
    except Exception:
        if tmp.exists(): tmp.unlink()
        raise

def new_task_id(tasks):
    import time as _t
    existing = {t['id'] for t in tasks}
    tid = f"t_{int(_t.time()*1000)}"
    while tid in existing:
        tid = tid + 'x'
    return tid

# ── Card groups ──────────────────────────────────────────────────────
def new_card_group_id(existing_ids=()):
    existing = set(existing_ids)
    while True:
        gid = 'g_' + secrets.token_hex(4)
        if gid not in existing:
            return gid

def default_card_group(name='群組 1'):
    return {
        'id':              new_card_group_id(),
        'name':            (name or '群組 1')[:30],
        'card_count':      6,
        'card_background': '',
        'cards':           []
    }

def normalize_card_group(group, fallback_name='群組 1'):
    name = str(group.get('name', '')).strip()[:30]
    gid  = str(group.get('id') or '')
    return {
        'id':              gid if gid else new_card_group_id(),
        'name':            name if name else fallback_name,
        'card_count':      max(1, min(24, int(group.get('card_count') or 6))),
        'card_background': str(group.get('card_background', '')),
        'cards':           group.get('cards', []) if isinstance(group.get('cards'), list) else []
    }

def migrate_cards_cfg(cfg):
    """Upgrade cfg from old single-group to multi-group format.
    Old fields (cards/card_count/card_background) are preserved.
    Returns (cfg, was_migrated).
    """
    if 'card_groups' in cfg:
        groups = [normalize_card_group(g, f'群組 {i+1}')
                  for i, g in enumerate(cfg.get('card_groups') or [])]
        if not groups:
            g = default_card_group('群組 1'); g['id'] = 'g_default'
            groups = [g]
        ids    = {g['id'] for g in groups}
        active = cfg.get('card_active_group_id', '')
        if active not in ids:
            active = groups[0]['id']
        cfg['card_groups']          = groups
        cfg['card_active_group_id'] = active
        return cfg, False
    # Old single-group format → wrap into card_groups
    old_count = max(1, min(24, int(cfg.get('card_count') or 6)))
    old_cards = cfg.get('cards', [])
    cfg['card_groups'] = [{
        'id':              'g_default',
        'name':            '群組 1',
        'card_count':      old_count,
        'card_background': cfg.get('card_background', ''),
        'cards':           old_cards if isinstance(old_cards, list) else []
    }]
    cfg['card_active_group_id'] = 'g_default'
    return cfg, True

def active_card_group(cfg):
    groups = cfg.get('card_groups') or []
    aid    = cfg.get('card_active_group_id', '')
    return next((g for g in groups if g['id'] == aid), groups[0] if groups else {})

# ── Scan ─────────────────────────────────────────────────────────────
def scan(dirs, recursive=False):
    out = []
    for d in dirs:
        p = Path(d)
        if not p.is_dir(): continue
        try:
            it = p.rglob('*') if recursive else p.iterdir()
            for f in it:
                if not f.is_file(): continue
                ext = f.suffix.lower()
                if ext not in ALL_EXT: continue
                if   ext in VIDEO_EXT: ftype = 'video'
                elif ext in AUDIO_EXT: ftype = 'audio'
                elif ext in IMAGE_EXT: ftype = 'image'
                elif ext in PDF_EXT:   ftype = 'pdf'
                elif ext in PPT_EXT:   ftype = 'ppt'
                else:                  ftype = 'doc'
                try:
                    st = f.stat()
                    out.append({'path':str(f),'name':f.name,'stem':f.stem,
                                'type':ftype,'ext':ext[1:].upper(),
                                'size':st.st_size,'mtime':st.st_mtime,'thumb':None})
                except: pass
        except PermissionError: pass
    out.sort(key=lambda x: x['mtime'], reverse=True)
    return out

# ── Thumbnail ─────────────────────────────────────────────────────────
def thumb_key(path, mtime):
    return hashlib.md5(f'{path}|{mtime}'.encode()).hexdigest() + '.jpg'

def gen_video_thumb(src, dst):
    try:
        r = subprocess.run(
            [FFMPEG_BIN,'-y','-i',src,'-ss','00:00:01',
             '-vf','scale=360:202:force_original_aspect_ratio=decrease,pad=360:202:(ow-iw)/2:(oh-ih)/2:black',
             '-frames:v','1', str(dst)],
            capture_output=True, timeout=20)
        return dst.exists() and dst.stat().st_size > 0
    except: return False

def gen_pdf_thumb(src, dst):
    try:
        import fitz
        doc = fitz.open(src)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.2,1.2))
        pix.save(str(dst)); doc.close()
        return dst.exists()
    except: return False

def gen_image_thumb(src, dst):
    try:
        from PIL import Image
        img = Image.open(src)
        img.thumbnail((360, 202), Image.LANCZOS)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        img.save(str(dst), 'JPEG', quality=85)
        return dst.exists()
    except: return False

def get_thumb(item):
    THUMB_DIR.mkdir(exist_ok=True)
    key = thumb_key(item['path'], item['mtime'])
    tp  = THUMB_DIR / key
    if tp.exists() and tp.stat().st_size > 0:
        return key
    if item['type'] == 'video' and gen_video_thumb(item['path'], tp): return key
    if item['type'] == 'pdf'   and gen_pdf_thumb(item['path'], tp):   return key
    if item['type'] == 'image' and gen_image_thumb(item['path'], tp): return key
    return None

# ── Open file ─────────────────────────────────────────────────────────
def open_file(path):
    if sys.platform == 'win32':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.run(['open', path])
    else:
        subprocess.run(['xdg-open', path])

# ── HTTP ──────────────────────────────────────────────────────────────
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, obj, status=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json;charset=utf-8')
        self.send_header('Content-Length', len(b))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        p = u.path

        if p == '/':
            html = HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html;charset=utf-8')
            self.send_header('Content-Length', len(html))
            self.end_headers(); self.wfile.write(html)

        elif p == '/api/files':
            cfg = load_cfg()
            rec = q.get('recursive',[None])[0]
            rec = cfg.get('recursive', False) if rec is None else rec == '1'
            files = scan(cfg['dirs'], rec)
            for f in files:
                f['thumb'] = get_thumb(f)
                if f['type'] == 'image' and not f['thumb']:
                    f['img_url'] = '/api/img?path=' + urllib.parse.quote(f['path'])
                else:
                    f['img_url'] = None
            self.send_json({'files': files, 'dirs': cfg['dirs'], 'recursive': rec})

        elif p == '/api/open':
            fp = q.get('path',[''])[0]
            if fp and Path(fp).exists():
                try: open_file(fp); self.send_json({'ok': True})
                except Exception as e: self.send_json({'ok':False,'err':str(e)})
            else: self.send_json({'ok':False,'err':'找不到檔案'})

        elif p == '/api/reveal':
            fp = q.get('path',[''])[0]
            if fp and sys.platform == 'win32':
                try: subprocess.Popen(['explorer','/select,', fp]); self.send_json({'ok':True})
                except Exception as e: self.send_json({'ok':False,'err':str(e)})
            else: self.send_json({'ok':False})

        elif p == '/api/thumb':
            key = q.get('key',[''])[0]
            tp  = THUMB_DIR / key
            if key and tp.exists() and key.endswith('.jpg'):
                data = tp.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type','image/jpeg')
                self.send_header('Content-Length', len(data))
                self.send_header('Cache-Control','public,max-age=3600')
                self.end_headers(); self.wfile.write(data)
            else: self.send_error(404)

        elif p == '/api/dirs':
            self.send_json(load_cfg()['dirs'])

        elif p == '/api/img':
            fp  = Path(q.get('path',[''])[0])
            cfg = load_cfg()
            ok  = any(str(fp).lower().startswith(d.lower()) for d in cfg['dirs'])
            if ok and fp.exists() and fp.suffix.lower() in IMAGE_MIME:
                mime = IMAGE_MIME.get(fp.suffix.lower(), 'image/jpeg')
                data = fp.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', len(data))
                self.send_header('Cache-Control', 'public,max-age=3600')
                self.end_headers(); self.wfile.write(data)
            else: self.send_error(404)

        elif p == '/api/tasks':
            self.send_json(load_tasks())

        elif p == '/api/browse':
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', 1)
                folder = filedialog.askdirectory(title='選擇要加入的媒體資料夾')
                root.destroy()
                if folder:
                    folder = str(Path(folder))  # normalize slashes
                    self.send_json({'ok': True, 'path': folder})
                else:
                    self.send_json({'ok': False, 'path': ''})
            except Exception as e:
                self.send_json({'ok': False, 'err': str(e)})

        elif p == '/api/cards':
            cfg = load_cfg()
            ag  = active_card_group(cfg)
            self.send_json({
                'card_groups':          cfg.get('card_groups', []),
                'card_active_group_id': cfg.get('card_active_group_id', ''),
                # backward-compatible projection of active group
                'cards':           ag.get('cards', []),
                'card_count':      ag.get('card_count', 6),
                'card_background': ag.get('card_background', ''),
            })

        elif p == '/api/card-image':
            fp = Path(q.get('path', [''])[0])
            if fp.exists() and fp.suffix.lower() in IMAGE_MIME:
                mime = IMAGE_MIME.get(fp.suffix.lower(), 'image/jpeg')
                data = fp.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', len(data))
                self.send_header('Cache-Control', 'public,max-age=3600')
                self.end_headers(); self.wfile.write(data)
            else: self.send_error(404)

        elif p == '/api/media':
            fp  = Path(q.get('path', [''])[0])
            ext = fp.suffix.lower() if fp.name else ''
            if not (fp.exists() and fp.is_file() and ext in MEDIA_MIME):
                self.send_error(404); return
            try:
                size = fp.stat().st_size
                mime = MEDIA_MIME.get(ext, 'application/octet-stream')
                rng  = self.headers.get('Range', '')
                start, end = 0, size - 1
                status = 200
                if rng.startswith('bytes='):
                    part = rng.split('=', 1)[1].split(',', 1)[0]
                    a, _, b = part.partition('-')
                    if a: start = int(a)
                    if b: end = int(b)
                    start = max(0, min(start, size - 1))
                    end   = max(start, min(end, size - 1))
                    status = 206
                length = end - start + 1
                self.send_response(status)
                self.send_header('Content-Type', mime)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(length))
                if status == 206:
                    self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                with fp.open('rb') as fh:
                    fh.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = fh.read(min(1024 * 512, remaining))
                        if not chunk: break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except Exception:
                self.send_error(404)

        elif p == '/api/file-thumb':
            fp  = Path(q.get('path', [''])[0])
            ext = fp.suffix.lower() if fp.name else ''
            if fp.exists() and fp.is_file() and ext in (VIDEO_EXT | IMAGE_EXT | PDF_EXT):
                ftype = ('video' if ext in VIDEO_EXT else
                         'image' if ext in IMAGE_EXT else 'pdf')
                try:
                    st   = fp.stat()
                    item = {'path': str(fp), 'type': ftype,
                            'mtime': st.st_mtime, 'ext': ext[1:].upper()}
                    key  = get_thumb(item)
                    if key:
                        data = (THUMB_DIR / key).read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(data))
                        self.send_header('Cache-Control', 'public,max-age=3600')
                        self.end_headers(); self.wfile.write(data)
                    else: self.send_error(404)
                except: self.send_error(404)
            else: self.send_error(404)

        elif p == '/api/browse-file':
            mode = q.get('mode', ['any'])[0]
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk(); root.withdraw()
                root.wm_attributes('-topmost', 1)
                if mode == 'image':
                    ft = [('圖片', '*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff *.tif'),
                          ('所有檔案', '*.*')]
                else:
                    ft = [('媒體檔案',
                           '*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.wmv *.flv '
                           '*.mp3 *.wav *.flac *.aac *.ogg *.m4a *.opus '
                           '*.pdf *.ppt *.pptx *.doc *.docx *.xls *.xlsx '
                           '*.jpg *.jpeg *.png *.gif *.bmp *.webp'),
                          ('所有檔案', '*.*')]
                path = filedialog.askopenfilename(title='選擇檔案', filetypes=ft)
                root.destroy()
                if path:
                    self.send_json({'ok': True, 'path': str(Path(path))})
                else:
                    self.send_json({'ok': False, 'path': ''})
            except Exception as e:
                self.send_json({'ok': False, 'err': str(e)})

        else: self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n)) if n else {}

        if u.path == '/api/dirs/add':
            d = body.get('dir','').strip()
            if d and Path(d).is_dir():
                cfg = load_cfg()
                if d not in cfg['dirs']: cfg['dirs'].append(d); save_cfg(cfg)
                self.send_json({'ok':True,'dirs':cfg['dirs']})
            else:
                self.send_json({'ok':False,'err':'目錄不存在: ' + d})

        elif u.path == '/api/dirs/remove':
            d = body.get('dir','')
            cfg = load_cfg()
            cfg['dirs'] = [x for x in cfg['dirs'] if x != d]
            save_cfg(cfg)
            self.send_json({'ok':True,'dirs':cfg['dirs']})

        elif u.path == '/api/dirs/remove-multiple':
            to_del = set(body.get('dirs', []))
            cfg = load_cfg()
            cfg['dirs'] = [x for x in cfg['dirs'] if x not in to_del]
            save_cfg(cfg)
            self.send_json({'ok':True,'dirs':cfg['dirs']})

        elif u.path == '/api/config/recursive':
            cfg = load_cfg()
            cfg['recursive'] = bool(body.get('recursive'))
            save_cfg(cfg)
            self.send_json({'ok':True,'recursive':cfg['recursive']})

        elif u.path == '/api/tasks/create':
            name = body.get('name','').strip()[:50]
            if not name:
                self.send_json({'ok':False,'err':'名稱不可為空'}); return
            data = load_tasks()
            tid  = new_task_id(data['tasks'])
            task = {'id':tid,'name':name,'currentIndex':-1,'items':[]}
            data['tasks'].append(task)
            if data['activeTaskId'] is None:
                data['activeTaskId'] = tid
            save_tasks(data)
            self.send_json({'ok':True,'task':task,'activeTaskId':data['activeTaskId']})

        elif u.path == '/api/tasks/rename':
            tid  = body.get('id','')
            name = body.get('name','').strip()[:50]
            if not name:
                self.send_json({'ok':False,'err':'名稱不可為空'}); return
            data = load_tasks()
            t = next((t for t in data['tasks'] if t['id']==tid), None)
            if not t:
                self.send_json({'ok':False,'err':'task not found'}); return
            t['name'] = name
            save_tasks(data)
            self.send_json({'ok':True})

        elif u.path == '/api/tasks/delete':
            tid  = body.get('id','')
            data = load_tasks()
            data['tasks'] = [t for t in data['tasks'] if t['id'] != tid]
            if data['activeTaskId'] == tid:
                data['activeTaskId'] = data['tasks'][0]['id'] if data['tasks'] else None
            save_tasks(data)
            self.send_json({'ok':True,'activeTaskId':data['activeTaskId']})

        elif u.path == '/api/tasks/save-items':
            tid   = body.get('id','')
            items = body.get('items',[])
            data  = load_tasks()
            t = next((t for t in data['tasks'] if t['id']==tid), None)
            if not t:
                self.send_json({'ok':False,'err':'task not found'}); return
            t['items'] = items
            save_tasks(data)
            self.send_json({'ok':True})

        elif u.path == '/api/tasks/set-active':
            tid  = body.get('id','')
            data = load_tasks()
            if not any(t['id']==tid for t in data['tasks']):
                self.send_json({'ok':False,'err':'task not found'}); return
            data['activeTaskId'] = tid
            save_tasks(data)
            self.send_json({'ok':True})

        elif u.path == '/api/tasks/set-current':
            tid   = body.get('id','')
            index = body.get('index', -1)
            data  = load_tasks()
            t = next((t for t in data['tasks'] if t['id']==tid), None)
            if not t:
                self.send_json({'ok':False,'err':'task not found'}); return
            t['currentIndex'] = index
            save_tasks(data)
            self.send_json({'ok':True})

        elif u.path == '/api/cards/save':
            cfg = load_cfg()
            if 'card_groups' in body:
                # New multi-group format
                groups = [normalize_card_group(g, f'群組 {i+1}')
                          for i, g in enumerate(body.get('card_groups') or [])]
                if not groups:
                    g = default_card_group('群組 1'); g['id'] = 'g_default'
                    groups = [g]
                ids    = {g['id'] for g in groups}
                active = body.get('card_active_group_id', '')
                if active not in ids:
                    active = groups[0]['id']
                cfg['card_groups']          = groups
                cfg['card_active_group_id'] = active
                ag = next((g for g in groups if g['id'] == active), groups[0])
                cfg['cards']          = ag.get('cards', [])
                cfg['card_count']     = ag.get('card_count', 6)
                cfg['card_background'] = ag.get('card_background', '')
            else:
                # Old single-group format → write into active group
                cards = body.get('cards', [])
                count = max(1, min(24, int(body.get('card_count') or 6)))
                bg    = body.get('card_background', '')
                cfg['cards']          = cards
                cfg['card_count']     = count
                cfg['card_background'] = bg
                ag = active_card_group(cfg)
                if ag:
                    ag['cards']          = cards
                    ag['card_count']     = count
                    ag['card_background'] = bg
            save_cfg(cfg)
            self.send_json({'ok': True})

        else: self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()


# ── Embedded HTML ─────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>媒體啟動器</title>
<style>
:root{
  --bg:#f5f5f7; --surf:#ffffff; --surf2:#f2f2f7; --surf3:#e8e8ed;
  --border:#d8d8de; --accent:#007aff; --acc2:#0068d9;
  --text:#1d1d1f; --muted:#6e6e73; --red:#ff3b30; --green:#34c759; --yellow:#ff9f0a;
  --shadow:0 10px 30px rgba(0,0,0,.08);
  --shadow-soft:0 4px 16px rgba(0,0,0,.06);
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:'Microsoft JhengHei','Segoe UI',system-ui,sans-serif;
  background:var(--bg);color:var(--text);display:flex;flex-direction:column}

/* ── Top bar ── */
.topbar{
  height:68px;background:rgba(255,255,255,.92);border-bottom:1px solid rgba(0,0,0,.08);
  display:flex;align-items:center;padding:0 20px;gap:14px;flex-shrink:0;
  backdrop-filter:saturate(180%) blur(18px);
  position:relative;z-index:900;
}
.logo{font-size:24px}
.logo-text{font-size:17px;font-weight:700;white-space:nowrap;letter-spacing:.01em}
.topbar-card-groups{
  display:flex;align-items:center;gap:8px;min-width:0;flex:1;
  max-width:none;
}
.topbar-card-groups.hidden{display:none}
.topbar-card-groups .kcard-group-tabs{
  padding:0;gap:6px;min-width:0;flex:1;
  overflow-x:auto;overflow-y:visible;scrollbar-width:none;
}
.topbar-card-groups .kcard-group-tabs::-webkit-scrollbar{display:none}
.topbar-card-groups .kcard-group-add{
  margin:0;width:34px;height:34px;background:#fff;
}
.topbar-card-actions{display:flex;align-items:center;gap:6px;flex-shrink:0}
.kcard-group-more-wrap{position:relative;flex-shrink:0}
.kcard-group-more{
  width:34px;height:34px;border-radius:999px;padding:0;
  justify-content:center;color:var(--muted);box-shadow:none;
  background:#fff;
}
.kcard-group-more:hover{color:var(--text);transform:none}
.kcard-group-popover{
  position:fixed;top:var(--kc-pop-top,72px);left:var(--kc-pop-left,240px);z-index:1200;
  width:280px;background:rgba(255,255,255,.98);
  border:1px solid rgba(0,0,0,.08);border-radius:20px;
  box-shadow:0 20px 50px rgba(0,0,0,.16);
  padding:12px;backdrop-filter:saturate(180%) blur(18px);
}
.kcard-group-popover.hidden{display:none}
.kcard-pop-title{font-size:14px;font-weight:800;margin-bottom:10px;color:var(--text)}
.kcard-pop-row{
  display:flex;align-items:center;justify-content:space-between;
  gap:10px;padding:8px 2px;border-top:1px solid rgba(0,0,0,.06);
}
.kcard-pop-row:first-of-type{border-top:none}
.kcard-pop-label{font-size:13px;font-weight:700;color:var(--muted)}
.kcard-pop-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.kcard-pop-small{
  padding:7px 11px;border-radius:999px;font-size:12px;font-weight:700;
  box-shadow:none;background:#fff;
}
.kcard-pop-small.danger{color:var(--red)}
.kcard-pop-count{min-width:24px;text-align:center;font-weight:800}
.kcard-delete-panel{
  margin-top:8px;padding-top:10px;border-top:1px solid rgba(0,0,0,.06);
  display:flex;flex-direction:column;gap:8px;
}
.kcard-delete-help{font-size:12px;line-height:1.45;color:var(--muted)}
.kcard-delete-list{
  max-height:220px;overflow-y:auto;display:flex;flex-direction:column;gap:6px;
  padding-right:2px;
}
.kcard-delete-choice{
  display:flex;align-items:center;gap:9px;padding:9px 10px;border-radius:14px;
  border:1px solid rgba(0,0,0,.07);background:rgba(248,248,250,.9);
  cursor:pointer;
}
.kcard-delete-choice:hover{background:#fff;border-color:rgba(0,122,255,.28)}
.kcard-delete-choice input{width:16px;height:16px;accent-color:var(--accent)}
.kcard-delete-choice span{
  flex:1;min-width:0;font-size:13px;font-weight:750;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.kcard-delete-choice small{font-size:11px;color:var(--muted)}
.kcard-delete-choice.active{box-shadow:inset 3px 0 0 rgba(0,122,255,.7)}
.kcard-delete-footer{display:flex;justify-content:flex-end;gap:6px;flex-wrap:wrap}

.search-wrap{position:relative;flex:1;max-width:420px}
.search-wrap input{
  width:100%;padding:11px 14px 11px 40px;background:var(--surf2);
  border:1px solid transparent;border-radius:16px;color:var(--text);
  font-size:15px;font-family:inherit;outline:none;transition:all .15s;
}
.search-wrap input:focus{background:#fff;border-color:rgba(0,122,255,.38);box-shadow:0 0 0 4px rgba(0,122,255,.12)}
.search-wrap .si{position:absolute;left:14px;top:50%;transform:translateY(-50%);
  color:var(--muted);font-size:16px;pointer-events:none}

.tabs{display:flex;gap:4px;background:var(--surf2);padding:5px;border-radius:18px}
.tab{
  padding:9px 15px;border-radius:14px;border:none;cursor:pointer;
  font-size:14px;font-weight:600;font-family:inherit;
  background:transparent;color:var(--muted);transition:all .15s;white-space:nowrap;
}
.tab.active{background:#fff;color:var(--text);box-shadow:var(--shadow-soft)}
.tab:hover:not(.active){color:var(--text)}

.topbar-right{margin-left:auto;display:flex;gap:8px;align-items:center}
.topbar-right > .hidden{display:none !important}
.advanced-tool.hidden{display:none !important}

button{
  display:inline-flex;align-items:center;gap:7px;padding:11px 16px;
  border-radius:16px;border:1px solid rgba(0,0,0,.08);cursor:pointer;
  font-size:14px;font-weight:650;font-family:inherit;
  background:#fff;color:var(--text);transition:all .15s;
  box-shadow:0 1px 2px rgba(0,0,0,.04);
}
button:hover{background:var(--surf2);transform:translateY(-1px)}
button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-blue{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-blue:hover{background:var(--acc2);border-color:var(--acc2)}
.btn-icon{padding:10px 13px;font-size:15px}

/* ── First-run guide ── */
.folder-coachmark{
  position:fixed;left:var(--coach-left,20px);top:var(--coach-top,84px);
  width:min(330px,calc(100vw - 32px));z-index:700;
  background:rgba(255,255,255,.97);border:1px solid rgba(0,0,0,.08);
  border-radius:22px;padding:15px 16px 15px 17px;
  box-shadow:0 20px 50px rgba(0,0,0,.16);
  backdrop-filter:saturate(180%) blur(18px);
  transition:opacity .18s,transform .18s;
}
.folder-coachmark.hidden{display:none}
.folder-coachmark::before{
  content:"";position:absolute;top:-22px;left:var(--arrow-x,42px);
  width:3px;height:23px;border-radius:999px;
  background:linear-gradient(180deg, rgba(0,122,255,0), var(--accent));
}
.folder-coachmark::after{
  content:"";position:absolute;top:-6px;left:calc(var(--arrow-x,42px) - 6px);
  width:12px;height:12px;background:var(--accent);
  transform:rotate(45deg);border-radius:3px;
}
.coach-kicker{
  display:inline-flex;align-items:center;gap:6px;
  color:var(--accent);font-size:12px;font-weight:800;letter-spacing:.08em;
  text-transform:uppercase;margin-bottom:5px;
}
.coach-title{font-size:16px;font-weight:800;color:var(--text);line-height:1.35}
.coach-text{font-size:13px;color:var(--muted);line-height:1.55;margin-top:4px}
.coach-close{
  position:absolute;right:10px;top:10px;width:28px;height:28px;
  padding:0;border-radius:999px;justify-content:center;
  background:var(--surf2);box-shadow:none;color:var(--muted);
}
.coach-close:hover{background:var(--surf3);transform:none;color:var(--text)}

/* ── Folder bar ── */
.folderbar{
  background:rgba(255,255,255,.86);border-bottom:1px solid rgba(0,0,0,.08);
  padding:14px 20px;display:flex;flex-direction:column;gap:10px;flex-shrink:0;
  backdrop-filter:saturate(180%) blur(14px);
}
.folderbar.hidden{display:none}
.dir-list{display:flex;flex-direction:column;gap:4px;max-height:220px;overflow-y:auto}
.dir-row{
  display:flex;align-items:center;gap:10px;padding:9px 12px;
  border-radius:14px;transition:background .12s;user-select:none;
}
.dir-row:hover{background:var(--surf2)}
.dir-row input[type="checkbox"]{
  width:18px;height:18px;cursor:pointer;accent-color:var(--accent);
  flex-shrink:0;border-radius:3px;
}
.dir-label{
  flex:1;font-size:14px;cursor:pointer;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;
}
.dir-label.active{color:var(--text)}
.dir-label.inactive{color:var(--muted)}
.dir-actions{
  display:flex;align-items:center;gap:8px;
  padding-top:8px;border-top:1px solid var(--border);margin-top:2px;
}
.dir-recursive{
  display:flex;align-items:center;gap:8px;
  color:var(--muted);font-size:14px;user-select:none;cursor:pointer;
  padding:9px 10px;border-radius:14px;
}
.dir-recursive:hover{background:var(--surf2);color:var(--text)}
.dir-recursive input{accent-color:var(--accent);cursor:pointer}
.btn-red{
  background:rgba(255,59,48,.08);color:#d70015;
  border-color:rgba(255,59,48,.2);
}
.btn-red:hover{background:rgba(255,59,48,.14);border-color:rgba(255,59,48,.34)}
.btn-red:disabled{opacity:.35;cursor:not-allowed;pointer-events:none}

/* ── Status bar ── */
.statusbar{
  padding:9px 20px;background:#fff;border-bottom:1px solid rgba(0,0,0,.07);
  font-size:13px;color:var(--muted);display:flex;align-items:center;gap:18px;
  flex-shrink:0;
}
.statusbar.hidden{display:none}
.stat-item{display:flex;align-items:center;gap:5px}

/* ── Main area (grid + sidebar) ── */
.main-area{flex:1;display:flex;flex-direction:row;overflow:hidden;min-height:0}
.grid-area{flex:1;overflow-y:auto;padding:22px;min-width:0;background:var(--bg)}

/* ── Task sidebar ── */
.task-sidebar{
  --task-sidebar-width:25vw;
  width:var(--task-sidebar-width);flex:0 0 var(--task-sidebar-width);min-width:0;
  position:relative;z-index:20;
  background:#fff;border-left:1px solid rgba(0,0,0,.08);
  display:flex;flex-direction:column;overflow:hidden;
}
.task-sidebar.toggling{transition:width .2s, flex-basis .2s}
.task-sidebar.hidden{width:0 !important;flex-basis:0 !important;min-width:0 !important;border-left:none;overflow:hidden}
.task-resize-handle{
  position:absolute;left:-8px;top:0;bottom:0;width:16px;
  cursor:col-resize;background:transparent;pointer-events:auto;
  touch-action:none;z-index:1000;
}
.task-resize-handle::after{
  content:"";position:absolute;top:0;bottom:0;left:8px;width:2px;
  background:transparent;transition:background .15s;
}
.task-resize-handle:hover,
.task-sidebar.resizing .task-resize-handle,
.task-sidebar.resize-edge-hover .task-resize-handle{background:rgba(47,129,247,.08)}
.task-resize-handle:hover::after,
.task-sidebar.resizing .task-resize-handle::after,
.task-sidebar.resize-edge-hover .task-resize-handle::after{background:var(--accent)}
body.resizing-task-sb{user-select:none;cursor:col-resize}
.task-sb-header{
  padding:14px 14px 12px;border-bottom:1px solid rgba(0,0,0,.08);
  display:flex;align-items:center;gap:8px;flex-shrink:0;
}
.task-sb-header select{
  flex:1;background:var(--surf2);border:1px solid transparent;
  border-radius:14px;color:var(--text);font-size:14px;
  font-family:inherit;padding:10px 12px;outline:none;cursor:pointer;
  min-width:0;
}
.task-sb-header select:focus{border-color:var(--accent)}
.task-sb-title{
  flex:1;font-size:13px;font-weight:600;color:var(--muted);
  padding:4px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.task-list{
  flex:1;overflow-y:auto;padding:14px;
  display:grid;grid-template-columns:1fr;align-content:start;gap:10px;
}
.task-empty{
  padding:28px 18px;text-align:center;color:var(--muted);font-size:14px;
  border:2px dashed var(--border);border-radius:18px;
  margin:12px;line-height:1.7;
}
.task-empty.drop-over{border-color:var(--accent);background:rgba(47,129,247,.06)}
.task-list.drop-over{background:rgba(47,129,247,.04)}
.task-item{
  display:flex;align-items:center;gap:12px;
  min-height:112px;padding:11px 12px 11px 10px;
  cursor:pointer;position:relative;overflow:hidden;
  background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:20px;
  border-left:4px solid transparent;
  transition:transform .16s,box-shadow .16s,border-color .16s,background .1s;
  box-shadow:0 2px 8px rgba(0,0,0,.04);
}
.task-item:hover{
  background:#fff;
  border-color:rgba(0,122,255,.38);
  box-shadow:var(--shadow-soft);
}
.task-item.current{
  border-color:rgba(0,122,255,.9);
  border-left-color:var(--accent);
  background:linear-gradient(90deg, rgba(0,122,255,.13), rgba(255,255,255,.96));
  box-shadow:0 0 0 3px rgba(0,122,255,.16), 0 14px 30px rgba(0,122,255,.14);
}
.task-item.current::after{
  content:"目前播放";
  position:absolute;right:8px;top:8px;z-index:3;
  padding:3px 8px;border-radius:999px;
  font-size:11px;font-weight:800;letter-spacing:.02em;
  color:#fff;background:var(--accent);
  box-shadow:0 4px 12px rgba(0,122,255,.28);
}
.task-item.next{
  border-left-color:rgba(0,122,255,.42);
  background:rgba(0,122,255,.035);
}
.task-item.missing{opacity:.58}
.task-item.dragging{opacity:.45}
.task-item.drag-over-top{border-top:2px solid var(--accent)}
.task-item.drag-over-bot{border-bottom:2px solid var(--accent)}
.task-item[draggable="true"]{cursor:grab}
.task-item[draggable="true"]:active{cursor:grabbing}
.ti-num{
  position:absolute;bottom:4px;left:4px;z-index:2;
  min-width:22px;height:20px;padding:0 6px;border-radius:6px;
  display:inline-flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;color:#fff;background:rgba(0,0,0,.68);
  backdrop-filter:blur(4px);
}
.ti-thumb{
  width:clamp(112px,34%,156px);aspect-ratio:16/9;flex:0 0 clamp(112px,34%,156px);
  overflow:hidden;position:relative;border-radius:14px;
  background:var(--surf2);
}
.task-item.current .ti-thumb{
  box-shadow:0 0 0 2px #fff, 0 0 0 4px rgba(0,122,255,.62);
}
.task-item.current .ti-num{background:var(--accent)}
.ti-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.ti-thumb .placeholder,
.ti-compact-ph{
  width:100%;height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:3px;
}
.ti-compact-ph{font-size:28px}
.ti-compact-ph .ph-ext{font-size:10px;padding:2px 6px}
.ti-body{
  flex:1;min-width:0;display:flex;flex-direction:column;gap:5px;
}
.ti-name{
  font-size:13px;font-weight:500;line-height:1.34;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;word-break:break-all;
}
.task-item.current .ti-name{
  color:var(--text);font-weight:750;
  padding-right:56px;
}
.ti-meta{
  display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);
  flex-wrap:wrap;
}
.ti-folder{
  max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}
.ti-status{
  font-size:10px;font-weight:700;border-radius:999px;padding:2px 7px;
  line-height:1.2;flex-shrink:0;
}
.ti-status.is-current{
  background:#fff;color:var(--accent);
  box-shadow:0 0 0 1px rgba(0,122,255,.35);
}
.ti-status.is-next{
  color:var(--accent);border:1px solid rgba(0,122,255,.45);
  background:rgba(0,122,255,.05);
}
.ti-warn{color:var(--red);font-size:12px;flex-shrink:0}
.ti-remove{
  opacity:0;font-size:12px;color:var(--muted);cursor:pointer;
  width:30px;height:30px;border-radius:999px;flex:0 0 30px;
  display:flex;align-items:center;justify-content:center;
  background:transparent;transition:all .1s;
}
.task-item:hover .ti-remove{opacity:1}
.ti-remove:hover{background:var(--red);color:#fff}
.task-sb-footer{
  padding:12px 14px;border-top:1px solid rgba(0,0,0,.08);
  display:flex;align-items:center;gap:6px;flex-shrink:0;
}
.task-sb-footer .count{font-size:12px;color:var(--muted);margin-left:auto}
.btn-task{
  background:#fff;border:1px solid rgba(0,0,0,.08);
  border-radius:14px;padding:10px 12px;font-size:14px;
  cursor:pointer;color:var(--text);transition:all .1s;
  box-shadow:0 1px 2px rgba(0,0,0,.04);
}
.btn-task:hover{background:var(--surf3)}
.btn-task.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.task-menu-wrap{position:relative}
.task-menu{
  position:absolute;right:0;top:calc(100% + 4px);
  background:#fff;border:1px solid rgba(0,0,0,.08);
  border-radius:16px;padding:6px;min-width:150px;
  box-shadow:var(--shadow);z-index:200;
}
.task-menu.hidden{display:none}
.task-menu button{
  display:block;width:100%;text-align:left;padding:10px 12px;
  border:none;background:transparent;border-radius:12px;
  font-size:13px;color:var(--text);cursor:pointer;
}
.task-menu button:hover{background:var(--surf3)}
.task-menu button.danger{color:#d70015}
.task-menu button.danger:hover{background:rgba(255,59,48,.1)}
@media(max-width:900px){
  .task-sidebar:not(.hidden){
    position:fixed;right:0;top:0;bottom:0;z-index:300;
    box-shadow:-14px 0 38px rgba(0,0,0,.18);
  }
}
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:18px;
}

/* ── Card ── */
.card{
  background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:22px;
  overflow:hidden;cursor:pointer;transition:transform .18s,box-shadow .18s,border-color .18s;
  position:relative;box-shadow:0 2px 8px rgba(0,0,0,.04);
}
.card.dragging{opacity:.55;transform:scale(.98)}
.card:hover{
  transform:translateY(-4px);
  box-shadow:var(--shadow);
  border-color:rgba(0,122,255,.34);
}
.card:active{transform:translateY(-2px)}

/* thumbnail */
.card-thumb{
  width:100%;aspect-ratio:16/9;overflow:hidden;position:relative;
  background:var(--surf2);
}
.card-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.card-thumb .placeholder{
  width:100%;height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:6px;
}
.ph-icon{font-size:36px;line-height:1}
.ph-ext{font-size:10px;font-weight:700;letter-spacing:.08em;
  padding:3px 8px;border-radius:999px;background:rgba(255,255,255,.78)}

/* Gradient by type */
.ph-video{background:linear-gradient(135deg,#fff1f0 0%,#ffd8d3 100%)}
.ph-audio{background:linear-gradient(135deg,#f4efff 0%,#dfd3ff 100%)}
.ph-image{background:linear-gradient(135deg,#ecfff6 0%,#c8f7df 100%)}
.ph-pdf  {background:linear-gradient(135deg,#eef6ff 0%,#cfe7ff 100%)}
.ph-ppt  {background:linear-gradient(135deg,#fff7e6 0%,#ffe1a8 100%)}
.ph-doc  {background:linear-gradient(135deg,#f1f8ef 0%,#d7f0d2 100%)}

/* reveal btn */
.card-reveal{
  position:absolute;top:9px;right:9px;
  width:34px;height:34px;border-radius:999px;
  background:rgba(255,255,255,.9);backdrop-filter:blur(8px);
  display:flex;align-items:center;justify-content:center;
  font-size:13px;border:none;padding:0;
  opacity:0;transition:opacity .15s;
  z-index:2;
}
.card:hover .card-reveal{opacity:1}
.card-reveal:hover{background:var(--surf3) !important;transform:none !important}

/* card body */
.card-body{padding:13px 14px 14px}
.card-name{
  font-size:14px;font-weight:650;line-height:1.38;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  margin-bottom:6px;word-break:break-all;
}
.card-meta{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
.type-badge{
  padding:3px 8px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.04em;
}
.tb-video{background:rgba(255,59,48,.1);color:#d70015}
.tb-audio{background:rgba(88,86,214,.1);color:#5856d6}
.tb-image{background:rgba(52,199,89,.12);color:#248a3d}
.tb-pdf  {background:rgba(0,122,255,.1);color:#0068d9}
.tb-ppt  {background:rgba(255,159,10,.14);color:#a05a00}
.tb-doc  {background:rgba(52,199,89,.12);color:#248a3d}

/* ── Empty / Loading ── */
.state-box{
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;gap:16px;text-align:center;padding:40px;
}
.state-icon{font-size:52px;line-height:1}
.state-title{font-size:17px;font-weight:600}
.state-sub{color:var(--muted);font-size:13px;line-height:1.7;max-width:400px}

/* ── Spinner ── */
@keyframes spin{to{transform:rotate(360deg)}}
.spinner{
  width:38px;height:38px;border:3px solid var(--surf3);
  border-top-color:var(--accent);border-radius:50%;
  animation:spin .8s linear infinite;
}

/* ── Toast ── */
.toast{
  position:fixed;bottom:24px;right:24px;
  background:rgba(255,255,255,.96);border:1px solid rgba(0,0,0,.08);
  border-radius:18px;padding:13px 18px;font-size:14px;
  box-shadow:var(--shadow);backdrop-filter:saturate(180%) blur(16px);
  opacity:0;transform:translateY(8px);
  transition:all .2s;pointer-events:none;z-index:999;
  max-width:320px;
}
.toast.show{opacity:1;transform:none}
.toast.err{border-color:rgba(255,59,48,.28);color:#d70015}
.toast.ok{border-color:rgba(52,199,89,.32);color:#248a3d}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#c7c7cc;border-radius:999px;border:3px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:var(--muted)}

/* ── 卡片模式 ── */
.kcard-view{display:flex;flex-direction:column;height:100%}
.kcard-controls{
  padding:13px 22px;background:rgba(255,255,255,.9);
  border-bottom:1px solid rgba(0,0,0,.08);
  display:flex;align-items:center;gap:12px;flex-shrink:0;
  backdrop-filter:saturate(180%) blur(14px);
}
.kcard-ctrl-label{font-size:13px;font-weight:600;color:var(--muted)}
.kcard-count-ctrl{display:flex;align-items:center;gap:6px}
.kcard-count-btn{
  width:30px;height:30px;border-radius:999px;padding:0;
  border:1px solid rgba(0,0,0,.10);background:#fff;
  cursor:pointer;font-size:18px;line-height:1;
  display:flex;align-items:center;justify-content:center;
  box-shadow:none;color:var(--text);transition:background .12s;
}
.kcard-count-btn:hover{background:var(--surf2);transform:none}
.kcard-count-num{font-size:15px;font-weight:700;min-width:26px;text-align:center}
.kcard-scroll{flex:1;overflow-y:auto;padding:22px}
.kcard-grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
  gap:18px;
}
.kcard{
  position:relative;border-radius:22px;overflow:hidden;cursor:pointer;
  aspect-ratio:16/9;background:var(--surf2);
  border:1px solid rgba(0,0,0,.08);box-shadow:0 2px 8px rgba(0,0,0,.04);
  transition:transform .18s,box-shadow .18s,border-color .18s;
}
.kcard:hover{
  transform:translateY(-4px) scale(1.01);
  box-shadow:0 18px 44px rgba(0,0,0,.14);
  border-color:rgba(0,122,255,.28);
}
.kcard.kcard-empty{border:2px dashed var(--border);background:transparent;box-shadow:none}
.kcard.kcard-empty:hover{border-color:rgba(0,122,255,.42);background:rgba(0,122,255,.03)}
.kcard-overlay{
  position:absolute;inset:0;z-index:1;
  background:linear-gradient(180deg,rgba(0,0,0,.04) 0%,rgba(0,0,0,.60) 100%);
}
.kcard-thumb-wrap{position:absolute;inset:0;z-index:0;overflow:hidden}
.kcard-thumb-wrap img{
  width:100%;height:100%;object-fit:cover;object-position:var(--thumb-pos,center center);
  display:block;
}
.kcard-empty-center{
  position:absolute;inset:0;z-index:1;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:8px;pointer-events:none;
}
.kcard-empty-icon{font-size:44px;font-weight:900;line-height:1;opacity:.10;color:var(--text)}
.kcard-empty-hint{font-size:12px;color:var(--muted);opacity:.55}
.kcard-footer{
  position:absolute;bottom:0;left:0;right:0;z-index:2;
  padding:14px 14px 13px;
}
.kcard.kcard-has-visual .kcard-footer{
  background:linear-gradient(0deg,rgba(0,0,0,.72) 0%,transparent 100%);
}
.kcard-title{
  font-size:15px;font-weight:700;line-height:1.3;
  color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.55);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}
.kcard.kcard-empty .kcard-title{color:var(--muted);text-shadow:none;font-weight:600;font-size:13px}
.kcard-file{
  margin-top:3px;font-size:11px;color:rgba(255,255,255,.70);
  text-shadow:0 1px 3px rgba(0,0,0,.5);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.kcard-edit-btn{
  position:absolute;top:10px;right:10px;z-index:3;
  width:36px;height:36px;border-radius:999px;padding:0;
  background:rgba(255,255,255,.90);backdrop-filter:blur(8px);
  border:none;cursor:pointer;
  opacity:0;transition:opacity .15s;
  display:flex;align-items:center;justify-content:center;
  font-size:15px;box-shadow:0 2px 8px rgba(0,0,0,.14);
  color:var(--text);
}
.kcard:hover .kcard-edit-btn{opacity:1}
.kcard-edit-btn:hover{background:#fff !important;transform:none !important}

/* ── 卡片編輯 modal ── */
.kc-modal-overlay{
  position:fixed;inset:0;z-index:800;
  background:rgba(0,0,0,.42);backdrop-filter:blur(6px);
  display:flex;align-items:center;justify-content:center;
}
.kc-modal-overlay.hidden{display:none}
.kc-modal-box{
  background:#fff;border-radius:24px;padding:26px 28px;
  width:min(500px,calc(100vw - 40px));max-height:90vh;overflow-y:auto;
  box-shadow:0 32px 80px rgba(0,0,0,.22);
  display:flex;flex-direction:column;gap:15px;
}
.kc-modal-hdr{display:flex;align-items:center;justify-content:space-between}
.kc-modal-title{font-size:17px;font-weight:700}
.kc-modal-close{
  width:32px;height:32px;border-radius:999px;background:var(--surf2);
  border:none;cursor:pointer;font-size:18px;
  display:flex;align-items:center;justify-content:center;
  padding:0;box-shadow:none;color:var(--muted);
}
.kc-modal-close:hover{background:var(--surf3);transform:none}
.kc-field-group{display:flex;flex-direction:column;gap:5px}
.kc-field-label{font-size:12px;font-weight:700;color:var(--muted);letter-spacing:.03em;text-transform:uppercase}
.kc-field-row{display:flex;gap:8px;align-items:center}
.kc-text-input{
  flex:1;padding:10px 13px;border-radius:14px;
  border:1px solid var(--border);background:var(--surf2);
  font-size:14px;color:var(--text);outline:none;font-family:inherit;
}
.kc-text-input:focus{border-color:var(--accent);background:#fff;box-shadow:0 0 0 3px rgba(0,122,255,.12)}
.kc-path-input{
  flex:1;padding:10px 13px;border-radius:14px;
  border:1px solid var(--border);background:var(--surf2);
  font-size:12px;color:var(--muted);outline:none;font-family:inherit;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:default;
  min-width:0;
}
.kc-pick-btn{
  padding:10px 14px;border-radius:14px;font-size:13px;white-space:nowrap;flex-shrink:0;
  background:#fff;border:1px solid rgba(0,0,0,.10);cursor:pointer;font-family:inherit;
  font-weight:600;transition:background .12s;box-shadow:none;color:var(--text);
}
.kc-pick-btn:hover{background:var(--surf2);transform:none}
.kc-pick-btn:disabled{opacity:.45;cursor:not-allowed}
.kc-preview-row{display:flex;align-items:center;gap:10px;min-height:22px}
.kc-preview-img{
  width:120px;height:68px;object-fit:cover;object-position:var(--thumb-pos,center center);border-radius:12px;
  border:1px solid var(--border);display:none;flex-shrink:0;
}
.kc-preview-img.show{display:block}
.kc-clear-btn{
  font-size:12px;color:var(--muted);background:none;border:none;
  cursor:pointer;padding:2px 4px;text-decoration:underline;
  box-shadow:none;font-family:inherit;
}
.kc-clear-btn:hover{color:var(--red);transform:none}
.kc-position-panel{
  display:flex;align-items:center;justify-content:space-between;gap:14px;
  padding:10px 12px;border:1px solid rgba(0,0,0,.08);border-radius:16px;
  background:rgba(248,248,250,.78);
}
.kc-position-copy{display:flex;flex-direction:column;gap:2px;min-width:0}
.kc-position-title{font-size:13px;font-weight:800;color:var(--text)}
.kc-position-hint{font-size:12px;color:var(--muted);line-height:1.35}
.kc-position-grid{
  display:grid;grid-template-columns:repeat(3,28px);gap:5px;flex-shrink:0;
}
.kc-position-btn{
  width:28px;height:28px;border-radius:9px;padding:0;box-shadow:none;
  background:#fff;border:1px solid rgba(0,0,0,.10);color:var(--muted);
  display:flex;align-items:center;justify-content:center;font-size:11px;
}
.kc-position-btn:hover{background:var(--surf2);transform:none;color:var(--text)}
.kc-position-btn.active{
  background:var(--accent);border-color:var(--accent);color:#fff;
}
.kc-modal-footer{
  display:flex;gap:8px;justify-content:flex-end;align-items:center;
  padding-top:12px;border-top:1px solid var(--border);
}
.kc-danger-btn{
  margin-right:auto;background:none;border:none;color:var(--red);
  font-size:13px;cursor:pointer;padding:4px 2px;box-shadow:none;
  text-decoration:underline;font-family:inherit;font-weight:600;
}
.kc-danger-btn:hover{color:#d70015;transform:none}

/* ── 群組分頁列 ── */
.kcard-group-row{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 22px 0;
  background:rgba(255,255,255,.9);backdrop-filter:saturate(180%) blur(14px);
  flex-shrink:0;flex-wrap:wrap;gap:6px;
  border-bottom:1px solid rgba(0,0,0,.06);
}
.kcard-group-tabs{
  display:flex;align-items:center;gap:5px;
  overflow-x:auto;flex:1;scrollbar-width:none;padding-bottom:8px;
}
.kcard-group-tabs::-webkit-scrollbar{display:none}
.kcard-group-tab{
  display:inline-flex;align-items:center;
  padding:6px 16px;border-radius:999px;
  font-size:13px;font-weight:600;color:var(--muted);
  background:transparent;border:1px solid transparent;
  cursor:pointer;white-space:nowrap;flex-shrink:0;box-shadow:none;
  transition:background .14s,color .14s,border-color .14s;
}
.kcard-group-tab:hover{background:var(--surf2);color:var(--text);transform:none}
.kcard-group-tab.active{
  background:#fff;color:var(--accent);
  border-color:rgba(0,122,255,.22);
  box-shadow:0 2px 8px rgba(0,0,0,.08);
}
.kcard-group-add{
  flex-shrink:0;width:30px;height:30px;border-radius:999px;
  border:1.5px dashed var(--border);background:transparent;
  font-size:17px;color:var(--muted);cursor:pointer;padding:0;
  box-shadow:none;display:inline-flex;align-items:center;justify-content:center;
  transition:background .14s,border-color .14s,color .14s;margin-bottom:8px;
}
.kcard-group-add:hover{background:var(--surf2);border-color:var(--accent);color:var(--accent);transform:none}
.kcard-group-actions{
  display:flex;align-items:center;gap:6px;flex-shrink:0;padding-bottom:8px;
}
.kcard-group-action-btn{
  padding:5px 12px;border-radius:999px;font-size:12px;font-weight:600;
  border:1px solid rgba(0,0,0,.10);background:#fff;cursor:pointer;
  color:var(--muted);box-shadow:none;white-space:nowrap;
  transition:background .12s,color .12s;
}
.kcard-group-action-btn:hover{background:var(--surf2);color:var(--text);transform:none}
.kcard-group-action-btn.danger:hover{
  background:rgba(255,59,48,.08);color:var(--red);
  border-color:rgba(255,59,48,.2);transform:none;
}
/* controls 緊接在群組列之後，移除重複的 border-bottom */
.kcard-group-row + .kcard-controls{border-bottom:1px solid rgba(0,0,0,.08)}

/* ── 卡片展示播放層 ── */
.kc-player{
  position:fixed;inset:0;z-index:1150;padding:88px 24px 24px;
  background:rgba(0,0,0,.08);border-radius:0;
  box-shadow:none;
  overflow:hidden;display:flex;flex-direction:column;
  backdrop-filter:saturate(160%) blur(18px);
}
.kc-player:fullscreen{padding:0;background:#111;backdrop-filter:none}
.kc-player.hidden{display:none}
.kc-player-stage{
  flex:1;min-height:0;display:flex;align-items:center;justify-content:center;
  padding:24px;background:#111;border-radius:28px 28px 0 0;
  box-shadow:0 28px 80px rgba(0,0,0,.32);overflow:hidden;
}
.kc-player:fullscreen .kc-player-stage{padding:0;border-radius:0;box-shadow:none}
.kc-player-stage img,
.kc-player-stage video,
.kc-player-stage iframe{
  max-width:100%;max-height:100%;border:0;border-radius:18px;
  box-shadow:0 18px 55px rgba(0,0,0,.35);
}
.kc-player-stage video{width:min(100%,1200px)}
.kc-player-stage iframe{width:100%;height:100%;background:#fff}
.kc-player:fullscreen .kc-player-stage img,
.kc-player:fullscreen .kc-player-stage video,
.kc-player:fullscreen .kc-player-stage iframe{
  width:100%;height:100%;max-width:none;max-height:none;
  border-radius:0;box-shadow:none;
}
.kc-player:fullscreen .kc-player-stage img{object-fit:contain}
.kc-player:fullscreen .kc-player-stage video{object-fit:contain}
.kc-player:fullscreen .kc-player-stage iframe{object-fit:fill}
.kc-player-audio{
  width:min(720px,90%);padding:36px;border-radius:24px;background:#1f1f23;
  display:flex;flex-direction:column;align-items:center;gap:18px;color:#fff;
}
.kc-player-audio-icon{font-size:64px}
.kc-player-audio audio{width:100%}
.kc-player-bar{
  display:flex;align-items:center;gap:10px;padding:14px 16px;
  background:rgba(255,255,255,.96);border-top:1px solid rgba(255,255,255,.14);
  border-radius:0 0 28px 28px;box-shadow:0 28px 80px rgba(0,0,0,.22);
}
.kc-player-title{
  flex:1;min-width:0;font-size:14px;font-weight:750;color:var(--text);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.kc-player-btn{
  padding:9px 14px;border-radius:999px;font-size:13px;font-weight:750;
  box-shadow:none;
}
.kc-player-close{background:var(--accent);color:#fff;border-color:var(--accent)}
.kc-player-nav{
  position:absolute;top:50%;z-index:5;transform:translateY(-50%);
  width:58px;height:58px;border-radius:999px;padding:0;
  display:flex;align-items:center;justify-content:center;
  font-size:30px;font-weight:800;color:#fff;
  background:rgba(0,0,0,.42);border:1px solid rgba(255,255,255,.18);
  box-shadow:0 12px 34px rgba(0,0,0,.28);
  opacity:0;pointer-events:none;transition:opacity .18s,background .15s;
  backdrop-filter:blur(10px);
}
.kc-player-nav.prev{left:22px}
.kc-player-nav.next{right:22px}
.kc-player.controls-visible .kc-player-nav,
.kc-player:not(:fullscreen):hover .kc-player-nav{opacity:1;pointer-events:auto}
.kc-player-nav:hover{background:rgba(0,122,255,.78);transform:translateY(-50%) scale(1.04)}
.kc-player.controls-visible .kc-player-bar{opacity:1}
.kc-player:fullscreen .kc-player-bar{
  position:absolute;left:18px;right:18px;bottom:18px;
  border-radius:22px;border-top:none;box-shadow:0 16px 48px rgba(0,0,0,.26);
  opacity:0;pointer-events:none;transform:translateY(12px);
  transition:opacity .18s,transform .18s;
}
.kc-player:fullscreen.controls-visible .kc-player-bar{
  opacity:1;pointer-events:auto;transform:none;
}
</style>
</head>
<body>

<!-- Top bar -->
<div class="topbar">
  <span class="logo">🎬</span>
  <span class="logo-text">媒體啟動器</span>

  <div class="topbar-card-groups hidden" id="topbarCardGroups"></div>

  <div class="search-wrap advanced-tool hidden">
    <span class="si">🔍</span>
    <input type="text" id="search" placeholder="搜尋檔案名稱..." oninput="filterRender()">
  </div>

  <div class="tabs advanced-tool hidden" id="tabs">
    <button class="tab active" data-type="all"   onclick="setTab(this)">全部</button>
    <button class="tab" data-type="video" onclick="setTab(this)">🎬 影片</button>
    <button class="tab" data-type="audio" onclick="setTab(this)">🎵 音樂</button>
    <button class="tab" data-type="image" onclick="setTab(this)">🖼 圖片</button>
    <button class="tab" data-type="pdf"   onclick="setTab(this)">📄 PDF</button>
    <button class="tab" data-type="ppt"   onclick="setTab(this)">📊 簡報</button>
    <button class="tab" data-type="doc"   onclick="setTab(this)">📝 文件</button>
  </div>

  <div class="topbar-right">
    <button class="advanced-tool hidden" onclick="toggleFolders()" title="管理資料夾" id="folderToggleBtn">📁 資料夾</button>
    <button class="advanced-tool hidden" onclick="toggleTaskSidebar()" title="任務播放清單" id="taskToggleBtn">📋 任務</button>
    <button class="hidden" id="cardModeBtn" onclick="toggleCardMode()" title="卡片模式">🃏 卡片</button>
    <button class="hidden" onclick="reload()" title="重新掃描" id="reloadBtn">⟳ 重新整理</button>
    <button class="hidden" onclick="toggleAdvancedTools()" title="顯示或隱藏管理工具" id="settingsBtn">⚙ 設定</button>
  </div>
</div>

<div class="folder-coachmark hidden" id="folderCoachmark">
  <button class="coach-close" onclick="dismissFolderGuide()" title="關閉提示">×</button>
  <div class="coach-kicker">開始使用</div>
  <div class="coach-title" id="coachTitle">先加入媒體資料夾</div>
  <div class="coach-text" id="coachText">先點右上角「設定」顯示管理工具，再點「資料夾」選擇放簡報、影片、音樂的資料夾。</div>
</div>

<!-- Folder management bar -->
<div class="folderbar hidden" id="folderbar">
  <div class="dir-list" id="dirList"></div>
  <div class="dir-actions">
    <button class="btn-blue" id="browseBtn" onclick="browseAndAdd()">📂 加入資料夾</button>
    <label class="dir-recursive" title="勾選後會掃描已加入資料夾底下所有子資料夾">
      <input type="checkbox" id="recursiveScan" onchange="setRecursiveScan(this.checked)">
      包含子資料夾
    </label>
    <span id="browseStatus" style="font-size:12px;color:var(--muted)"></span>
    <button class="btn-red" id="deleteBtn" onclick="deleteChecked()" disabled
            style="margin-left:auto">🗑 刪除勾選的資料夾 (0)</button>
  </div>
</div>

<!-- Status -->
<div class="statusbar hidden" id="statusbar">
  <span class="stat-item">📂 <span id="statDirs">-</span> 個資料夾</span>
  <span class="stat-item">📄 <span id="statTotal">-</span> 個檔案</span>
  <span class="stat-item" id="statFiltered" style="display:none">🔎 顯示 <span id="statFilteredN">-</span> 個</span>
</div>

<!-- Main area: grid + task sidebar -->
<div class="main-area">

  <!-- Grid -->
  <div class="grid-area" id="gridArea">
    <div class="state-box">
      <div class="spinner"></div>
      <div class="state-title">載入中…</div>
    </div>
  </div>

  <!-- Task sidebar -->
  <div class="task-sidebar hidden" id="taskSidebar">
    <div class="task-resize-handle" id="taskResizeHandle"
         role="separator" aria-orientation="vertical"
         aria-label="調整任務側欄寬度" title="拖曳調整寬度，雙擊恢復預設"></div>
    <div class="task-sb-header">
      <select id="taskSelect" onchange="switchTask(this.value)">
        <option value="">（無任務）</option>
      </select>
      <button class="btn-task" onclick="promptCreateTask()" title="新增任務">＋</button>
      <div class="task-menu-wrap">
        <button class="btn-task" id="taskMenuBtn" onclick="toggleTaskMenu(event)" title="任務選項">⋯</button>
        <div class="task-menu hidden" id="taskMenu">
          <button onclick="promptRenameTask()">✏ 改名</button>
          <button class="danger" onclick="confirmDeleteTask()">🗑 刪除此任務</button>
        </div>
      </div>
    </div>
    <div class="task-list" id="taskList">
      <div class="task-empty" id="taskEmpty">拖曳左側媒體卡片到此處加入清單</div>
    </div>
    <div class="task-sb-footer">
      <button class="btn-task" id="playCurrentBtn" onclick="playCurrentItem()" disabled>▶ 播放目前</button>
      <button class="btn-task" id="playNextBtn" onclick="playNextItem()" disabled>▶▶ 下一個</button>
      <span class="count" id="taskCount">0 項</span>
    </div>
  </div>

</div>

<!-- Card mode editor modal -->
<div class="kc-modal-overlay hidden" id="kcModal"
     onclick="if(event.target===this)closeKcModal()">
  <div class="kc-modal-box">
    <div class="kc-modal-hdr">
      <span class="kc-modal-title" id="kcModalTitle">編輯卡片</span>
      <button class="kc-modal-close" onclick="closeKcModal()">×</button>
    </div>

    <div class="kc-field-group">
      <div class="kc-field-label">標題（留空則自動顯示檔名）</div>
      <input type="text" class="kc-text-input" id="kcEdit-title" placeholder="卡片標題（選填）">
    </div>

    <div class="kc-field-group">
      <div class="kc-field-label">播放檔案</div>
      <div class="kc-field-row">
        <input type="text" class="kc-path-input" id="kcEdit-file" readonly placeholder="尚未選擇">
        <button class="kc-pick-btn" onclick="kcBrowse(this,'file')">選擇…</button>
      </div>
    </div>

    <div class="kc-field-group">
      <div class="kc-field-label">縮圖（選填，不填則自動產生）</div>
      <div class="kc-field-row">
        <input type="text" class="kc-path-input" id="kcEdit-thumb" readonly placeholder="尚未選擇">
        <button class="kc-pick-btn" onclick="kcBrowse(this,'thumbnail')">選擇…</button>
      </div>
      <div class="kc-preview-row">
        <img class="kc-preview-img" id="kcPrev-thumb" alt="縮圖預覽">
        <button class="kc-clear-btn" onclick="kcClearField('thumbnail')">清除縮圖</button>
      </div>
      <div class="kc-position-panel">
        <div class="kc-position-copy">
          <div class="kc-position-title">縮圖焦點</div>
          <div class="kc-position-hint">直式圖片可選上方或下方，讓主體留在卡片內。</div>
        </div>
        <div class="kc-position-grid" id="kcThumbPositionGrid"></div>
      </div>
    </div>

    <div class="kc-modal-footer">
      <button class="kc-danger-btn" onclick="clearKcCard()">🗑 清除此卡片</button>
      <button onclick="closeKcModal()">取消</button>
      <button class="btn-blue" onclick="saveKcCard()">儲存</button>
    </div>
  </div>
</div>

<div class="kc-player hidden" id="kcPlayer" onmousemove="showKcPlayerControls()" onclick="handleKcPlayerBackdropClick(event)">
  <button class="kc-player-nav prev" onclick="playAdjacentKCard(-1)" title="上一個">‹</button>
  <button class="kc-player-nav next" onclick="playAdjacentKCard(1)" title="下一個">›</button>
  <div class="kc-player-stage" id="kcPlayerStage"></div>
  <div class="kc-player-bar">
    <button class="kc-player-btn" onclick="playAdjacentKCard(-1)">← 上一個</button>
    <div class="kc-player-title" id="kcPlayerTitle">未播放</div>
    <button class="kc-player-btn" onclick="openCurrentKCardExternal()">外部開啟</button>
    <button class="kc-player-btn" id="kcFullscreenBtn" onclick="toggleKCardFullscreen()">全螢幕</button>
    <button class="kc-player-btn" onclick="playAdjacentKCard(1)">下一個 →</button>
    <button class="kc-player-btn kc-player-close" onclick="closeKCardPlayer()">關閉</button>
  </div>
</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
'use strict';
let allFiles    = [];
let allDirs     = [];
let fileMap     = new Map();
let checkedDirs = new Set();
let recursiveScan = false;
let folderGuideDismissed = localStorage.getItem('folderGuideDismissed') === '1';
let advancedToolsVisible = localStorage.getItem('advancedToolsVisible') === '1';
let activeType  = 'all';
const MEDIA_DRAG_TYPE = 'application/x-media-item';
const TASK_DRAG_TYPE  = 'application/x-task-reorder';
let cardDragActive    = false;
let draggingTaskIndex = null;

// ── Task sidebar resize constants ─────────────────────────────────
const TASK_SB_MIN     = 240;
const TASK_SB_DEFAULT = 320;
const TASK_SB_MAX_ABS = 640;
let taskSbStoredWidth = TASK_SB_DEFAULT;  // in-memory width; applied to DOM only when sidebar is open

function mediaTaskItem(f) {
  return {path:f.path, name:f.name, stem:f.stem, type:f.type, ext:f.ext};
}

function rebuildFileMap() {
  fileMap = new Map(allFiles.map(f => [f.path, f]));
}

function getTaskItemVisual(item) {
  const f = fileMap.get(item.path);
  return f ? {...f, missing:false} : {...item, thumb:null, img_url:null, missing:true};
}

function taskThumbHtml(item) {
  const visual = getTaskItemVisual(item);
  const type = visual.type || item.type || 'doc';
  const ext = visual.ext || item.ext || '';
  if (visual.thumb) {
    return `<img src="/api/thumb?key=${encodeURIComponent(visual.thumb)}"
                 alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=placeholderHtml('${type}','${ext}')">`;
  }
  if (visual.img_url) {
    return `<img src="${visual.img_url}" alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=placeholderHtml('${type}','${ext}')">`;
  }
  return placeholderHtml(type, ext);
}

function compactPlaceholderHtml(type, ext) {
  const icons = {video:'🎬', audio:'🎵', image:'🖼', pdf:'📄', ppt:'📊', doc:'📝'};
  return `<div class="ti-compact-ph ph-${type}">
    <span>${icons[type]||'📁'}</span>
    <span class="ph-ext">${escHtml(ext)}</span>
  </div>`;
}

function taskCompactThumbHtml(item) {
  const visual = getTaskItemVisual(item);
  const type = visual.type || item.type || 'doc';
  const ext = visual.ext || item.ext || '';
  const fallback = `compactPlaceholderHtml(${JSON.stringify(type)},${JSON.stringify(ext)})`;
  if (visual.thumb) {
    return `<img src="/api/thumb?key=${encodeURIComponent(visual.thumb)}"
                 alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=${escHtml(fallback)}">`;
  }
  if (visual.img_url) {
    return `<img src="${visual.img_url}" alt="" loading="lazy"
                 onerror="this.parentElement.innerHTML=${escHtml(fallback)}">`;
  }
  return compactPlaceholderHtml(type, ext);
}

function getNextTaskIndex(task) {
  if (!task || task.items.length === 0) return -1;
  if (task.currentIndex < 0) return 0;
  return (task.currentIndex + 1) % task.items.length;
}

function taskFolderName(item) {
  const parts = (item.path || '').replace(/\//g,'\\').split('\\');
  return parts.length >= 2 ? parts[parts.length - 2] : '';
}

function renderTaskItemCompact(item, i, currentIndex, nextIndex) {
  const visual = getTaskItemVisual(item);
  const type = visual.type || item.type || 'doc';
  const ext = (visual.ext || item.ext || '').toUpperCase();
  const isCurrent = i === currentIndex;
  const isNext = !isCurrent && i === nextIndex;
  const missing = visual.missing;
  const stateClass = isCurrent ? ' current' : isNext ? ' next' : '';
  const missClass = missing ? ' missing' : '';
  const folder = taskFolderName(item);
  const badge = `<span class="type-badge tb-${type}">${escHtml(ext)}</span>`;
  const folderSpan = folder
    ? `<span class="ti-folder" title="${escHtml(item.path)}">${escHtml(folder)}</span>`
    : '';
  const warnHtml = missing ? '<span class="ti-warn">未在目前清單中</span>' : '';
  const statusHtml = isCurrent
    ? '<span class="ti-status is-current">目前</span>'
    : isNext
      ? '<span class="ti-status is-next">下一個</span>'
      : '';

  return `<div class="task-item${stateClass}${missClass}" data-index="${i}" draggable="true"
               onclick="playTaskItem(${i})"
               ondragstart="startTaskItemDrag(event,${i})"
               ondragover="overTaskItem(event,${i})"
               ondragleave="clearTaskDropMarks(event)"
               ondrop="dropOnTaskItem(event,${i})"
               ondragend="endTaskItemDrag()">
    <div class="ti-thumb ph-${type}">
      <span class="ti-num">${i + 1}</span>
      ${taskCompactThumbHtml(item)}
    </div>
    <div class="ti-body">
      <div class="ti-name" title="${escHtml(item.path)}">${escHtml(item.stem || item.name)}</div>
      <div class="ti-meta">${badge}${folderSpan}${warnHtml}${statusHtml}</div>
    </div>
    <span class="ti-remove" onclick="removeTaskItem(event,${i})"
          ondragstart="event.stopPropagation()" title="從清單移除">✕</span>
  </div>`;
}
// ── Task state ────────────────────────────────────────────────────
let taskState = { activeTaskId: null, tasks: [] };
const activeTask  = () => taskState.tasks.find(t => t.id === taskState.activeTaskId) || null;
const taskById    = id => taskState.tasks.find(t => t.id === id) || null;
const TYPE_ICON   = {video:'🎬',audio:'🎵',image:'🖼',pdf:'📄',ppt:'📊',doc:'📝'};

// ── Init ──────────────────────────────────────────────────────────
async function init() {
  cardModeActive = true;
  localStorage.setItem('cardModeActive', '1');
  applyAdvancedToolsVisibility();
  loadTaskSidebarWidth();
  initTaskSidebarResize();
  setupTaskDropZone();
  await Promise.all([reload(), loadTasks(), loadCards()]);
  if (cardModeActive) {
    document.getElementById('cardModeBtn').classList.add('active');
    renderCardMode();
  }
}

function applyAdvancedToolsVisibility() {
  document.querySelectorAll('.advanced-tool')
    .forEach(el => el.classList.toggle('hidden', !advancedToolsVisible));

  const status = document.getElementById('statusbar');
  if (status) status.classList.toggle('hidden', !advancedToolsVisible);

  const settingsBtn = document.getElementById('settingsBtn');
  if (settingsBtn) {
    settingsBtn.classList.toggle('active', advancedToolsVisible);
    settingsBtn.title = advancedToolsVisible ? '隱藏管理工具' : '顯示管理工具';
  }

  if (!advancedToolsVisible) {
    const folderbar = document.getElementById('folderbar');
    if (folderbar) folderbar.classList.add('hidden');
    const sb = document.getElementById('taskSidebar');
    const taskBtn = document.getElementById('taskToggleBtn');
    if (sb && !sb.classList.contains('hidden')) sb.classList.add('hidden');
    if (taskBtn) taskBtn.classList.remove('active');
  }

  updateFolderGuide();
}

function toggleAdvancedTools() {
  advancedToolsVisible = !advancedToolsVisible;
  localStorage.setItem('advancedToolsVisible', advancedToolsVisible ? '1' : '0');
  applyAdvancedToolsVisibility();
}

function setupTaskDropZone() {
  const list = document.getElementById('taskList');
  if (!list || list.dataset.dropReady) return;
  list.dataset.dropReady = '1';

  list.addEventListener('dragover', e => {
    if (!hasDragType(e, MEDIA_DRAG_TYPE)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    list.classList.add('drop-over');
    const empty = document.getElementById('taskEmpty');
    if (empty && list.contains(empty)) empty.classList.add('drop-over');
  });

  list.addEventListener('dragleave', e => {
    if (list.contains(e.relatedTarget)) return;
    clearTaskDropState();
  });

  list.addEventListener('drop', e => {
    if (!hasDragType(e, MEDIA_DRAG_TYPE)) return;
    e.preventDefault();
    clearTaskDropState();
    const item = readMediaDragItem(e);
    if (item) addItemToActiveTask(item);
  });
}

function dismissFolderGuide() {
  folderGuideDismissed = true;
  localStorage.setItem('folderGuideDismissed', '1');
  const mark = document.getElementById('folderCoachmark');
  if (mark) mark.classList.add('hidden');
}

function updateFolderGuide() {
  const mark = document.getElementById('folderCoachmark');
  if (!mark || folderGuideDismissed) return;
  if (!advancedToolsVisible) {
    mark.classList.add('hidden');
    return;
  }
  const shouldShow = allFiles.length === 0;
  if (!shouldShow) {
    mark.classList.add('hidden');
    return;
  }

  const folderbar = document.getElementById('folderbar');
  const folderbarOpen = folderbar && !folderbar.classList.contains('hidden');
  const target = folderbarOpen
    ? document.getElementById('browseBtn')
    : document.getElementById('folderToggleBtn');
  if (!target) return;

  const title = document.getElementById('coachTitle');
  const text = document.getElementById('coachText');
  if (folderbarOpen) {
    title.textContent = '選擇放媒體的資料夾';
    text.textContent = '按「加入資料夾」選取簡報、影片、音樂所在位置。若資料分散在子資料夾，也可以勾選「包含子資料夾」。';
  } else {
    title.textContent = '先開啟設定，再加入資料夾';
    text.textContent = '點右上角「設定」顯示管理工具，再點「資料夾」選擇放簡報、影片、音樂的資料夾。';
  }

  const rect = target.getBoundingClientRect();
  const width = Math.min(330, window.innerWidth - 32);
  const targetCenter = rect.left + rect.width / 2;
  const left = Math.max(16, Math.min(window.innerWidth - width - 16, targetCenter - width * 0.5));
  const top = rect.bottom + 18;
  mark.style.setProperty('--coach-left', left + 'px');
  mark.style.setProperty('--coach-top', top + 'px');
  mark.style.setProperty('--arrow-x', Math.max(24, Math.min(width - 24, targetCenter - left)) + 'px');
  mark.classList.remove('hidden');
}

// ── Load files ────────────────────────────────────────────────────
async function reload() {
  const btn = document.getElementById('reloadBtn');
  if (btn) { btn.textContent = '⟳ 載入中…'; btn.disabled = true; }
  try {
    const r = await fetch('/api/files?recursive=' + (recursiveScan ? '1' : '0'));
    const d = await r.json();
    const prevDirs = new Set(allDirs);
    allDirs  = d.dirs  || [];
    allFiles = d.files || [];
    recursiveScan = !!d.recursive;
    const recEl = document.getElementById('recursiveScan');
    if (recEl) recEl.checked = recursiveScan;
    rebuildFileMap();
    // New dirs that weren't in the list before: auto-check them
    allDirs.forEach(dir => { if (!prevDirs.has(dir)) checkedDirs.add(dir); });
    // Remove stale dirs from checked set
    [...checkedDirs].forEach(dir => { if (!allDirs.includes(dir)) checkedDirs.delete(dir); });
    document.getElementById('statDirs').textContent  = allDirs.length;
    document.getElementById('statTotal').textContent = allFiles.length;
    renderDirList();
    filterRender();
    renderTaskSidebar();
    updateFolderGuide();
  } catch {
    showGrid([]); toast('無法連線到伺服器', 'err');
    updateFolderGuide();
  }
  if (btn) { btn.textContent = '⟳ 重新整理'; btn.disabled = false; }
}

// ── Filter & render ───────────────────────────────────────────────
function filterRender() {
  const q = document.getElementById('search').value.trim().toLowerCase();
  let list = allFiles;
  // Filter by checked dirs
  if (checkedDirs.size < allDirs.length) {
    list = list.filter(f => {
      const fp = f.path.replace(/\//g,'\\').toLowerCase();
      return [...checkedDirs].some(dir => fp.startsWith(dir.toLowerCase()));
    });
  }
  if (activeType !== 'all') list = list.filter(f => f.type === activeType);
  if (q) list = list.filter(f => f.name.toLowerCase().includes(q));
  const sf  = document.getElementById('statFiltered');
  const sfn = document.getElementById('statFilteredN');
  if (list.length < allFiles.length) {
    sf.style.display = ''; sfn.textContent = list.length;
  } else { sf.style.display = 'none'; }
  showGrid(list);
}

function setTab(el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  activeType = el.dataset.type;
  filterRender();
}

// ── Render grid ───────────────────────────────────────────────────
function showGrid(files) {
  const area = document.getElementById('gridArea');
  if (!files.length) {
    area.innerHTML = `
      <div class="state-box">
        <div class="state-icon">🗂️</div>
        <div class="state-title">沒有找到檔案</div>
        <div class="state-sub">
          主畫面以「群組 1」卡片為主。請點卡片右上角「✏」設定播放檔案；需要調整卡片數量或背景時，請點群組旁的「⋯」。<br>
          支援：圖片、影片、音樂、PDF；簡報與文件會以外部程式開啟。
        </div>
      </div>`;
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'grid';

  files.forEach(f => {
    const card = document.createElement('div');
    card.className = 'card';
    card.title = f.path;
    card.draggable = true;

    const thumbHtml = f.thumb
      ? `<img src="/api/thumb?key=${encodeURIComponent(f.thumb)}"
               alt="" loading="lazy"
               onerror="this.parentElement.innerHTML=placeholderHtml('${f.type}','${f.ext}')">`
      : f.img_url
        ? `<img src="${f.img_url}" alt="" loading="lazy"
                onerror="this.parentElement.innerHTML=placeholderHtml('${f.type}','${f.ext}')">`
        : placeholderHtml(f.type, f.ext);

    const badge = `<span class="type-badge tb-${f.type}">${f.ext}</span>`;
    const size  = fmtSize(f.size);
    const date  = new Date(f.mtime * 1000).toLocaleDateString('zh-TW');

    card.innerHTML = `
      <div class="card-thumb ph-${f.type}">
        ${thumbHtml}
        <button class="card-reveal" onclick="reveal(event,'${esc(f.path)}')" title="在資料夾中顯示">📂</button>
      </div>
      <div class="card-body">
        <div class="card-name">${escHtml(f.stem)}</div>
        <div class="card-meta">${badge}<span>${size}</span><span>${date}</span></div>
      </div>`;

    card.addEventListener('dragstart', e => {
      cardDragActive = true;
      e.dataTransfer.effectAllowed = 'copy';
      e.dataTransfer.setData(MEDIA_DRAG_TYPE, JSON.stringify(mediaTaskItem(f)));
      e.dataTransfer.setData('text/plain', f.path);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      setTimeout(() => { cardDragActive = false; }, 0);
    });
    card.addEventListener('click', () => {
      if (cardDragActive) return;
      openFile(f.path);
    });
    grid.appendChild(card);
  });

  area.innerHTML = '';
  area.appendChild(grid);
}

function placeholderHtml(type, ext) {
  const icons  = {video:'🎬', audio:'🎵', image:'🖼', pdf:'📄', ppt:'📊', doc:'📝'};
  const colors = {video:'#d70015', audio:'#5856d6', image:'#248a3d',
                  pdf:'#0068d9', ppt:'#a05a00', doc:'#248a3d'};
  return `<div class="placeholder">
    <div class="ph-icon">${icons[type]||'📁'}</div>
    <div class="ph-ext" style="color:${colors[type]||'#6e6e73'}">${ext}</div>
  </div>`;
}

// ── Actions ───────────────────────────────────────────────────────
async function openFile(path) {
  try {
    const r = await fetch('/api/open?path=' + encodeURIComponent(path));
    const d = await r.json();
    if (!d.ok) toast('開啟失敗: ' + (d.err||''), 'err');
    else toast('已開啟 ' + path.split('\\').pop(), 'ok');
  } catch { toast('無法連線', 'err'); }
}

async function reveal(e, path) {
  e.stopPropagation();
  try { await fetch('/api/reveal?path=' + encodeURIComponent(path)); }
  catch {}
}

// ── Folder management ─────────────────────────────────────────────
function toggleFolders() {
  document.getElementById('folderbar').classList.toggle('hidden');
  requestAnimationFrame(updateFolderGuide);
}

function renderDirList() {
  const list = document.getElementById('dirList');
  if (!allDirs.length) {
    list.innerHTML = '<div style="padding:6px 8px;color:var(--muted);font-size:13px">尚無資料夾，請點「加入資料夾」</div>';
    updateDeleteBtn(); return;
  }
  list.innerHTML = allDirs.map((d, i) => {
    const on = checkedDirs.has(d);
    const id = 'dc' + i;
    return `<div class="dir-row">
      <input type="checkbox" id="${id}" ${on?'checked':''} onchange="toggleDir('${esc(d)}',this.checked)">
      <label class="dir-label ${on?'active':'inactive'}" for="${id}">📁 ${escHtml(d)}</label>
    </div>`;
  }).join('');
  updateDeleteBtn();
}

function updateDeleteBtn() {
  const n   = checkedDirs.size;
  const btn = document.getElementById('deleteBtn');
  btn.textContent = `🗑 刪除勾選的資料夾 (${n})`;
  btn.disabled    = (n === 0);
}

function toggleDir(dir, isChecked) {
  if (isChecked) checkedDirs.add(dir);
  else           checkedDirs.delete(dir);
  renderDirList();
  filterRender();
}

async function setRecursiveScan(on) {
  recursiveScan = !!on;
  try {
    const r = await fetch('/api/config/recursive', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({recursive: recursiveScan})
    });
    const d = await r.json();
    if (!d.ok) throw new Error();
    toast(recursiveScan ? '已開啟：包含子資料夾' : '已關閉：只掃描第一層', 'ok');
    reload();
  } catch {
    toast('無法儲存子資料夾設定', 'err');
    recursiveScan = !recursiveScan;
    const recEl = document.getElementById('recursiveScan');
    if (recEl) recEl.checked = recursiveScan;
  }
}

async function browseAndAdd() {
  const btn    = document.getElementById('browseBtn');
  const status = document.getElementById('browseStatus');
  btn.disabled = true; btn.textContent = '⏳ 開啟中…'; status.textContent = '';
  try {
    const r = await fetch('/api/browse');
    const d = await r.json();
    if (!d.ok || !d.path) { btn.disabled = false; btn.textContent = '📂 加入資料夾'; return; }
    const r2 = await fetch('/api/dirs/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({dir: d.path})
    });
    const d2 = await r2.json();
    if (d2.ok) { toast('已加入：' + d.path, 'ok'); reload(); }
    else        { toast(d2.err || '加入失敗', 'err'); }
  } catch { toast('無法連線伺服器', 'err'); }
  btn.disabled = false; btn.textContent = '📂 加入資料夾';
}

async function deleteChecked() {
  if (!checkedDirs.size) return;
  const toDelete = [...checkedDirs];
  const names    = toDelete.map(p => '・' + p).join('\n');
  const msg      = `確定要從啟動器移除以下 ${toDelete.length} 個資料夾？\n\n${names}\n\n（電腦上的實際檔案不會被刪除）`;
  if (!confirm(msg)) return;
  try {
    const r = await fetch('/api/dirs/remove-multiple', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({dirs: toDelete})
    });
    const d = await r.json();
    if (d.ok) {
      toDelete.forEach(dir => checkedDirs.delete(dir));
      toast(`已移除 ${toDelete.length} 個資料夾`, 'ok');
      reload();
    } else { toast(d.err || '刪除失敗', 'err'); }
  } catch { toast('無法連線伺服器', 'err'); }
}

// ── Task sidebar toggle ───────────────────────────────────────────
// ── Task sidebar resize (Phase A+B) ──────────────────────────────
function clampTaskSidebarWidth(px) {
  const viewportMax = Math.floor(window.innerWidth * 0.5);
  const max = Math.max(TASK_SB_MIN, Math.min(TASK_SB_MAX_ABS, viewportMax));
  const n = Number(px);
  if (!Number.isFinite(n)) return defaultTaskSidebarWidth();
  return Math.min(max, Math.max(TASK_SB_MIN, Math.round(n)));
}

function defaultTaskSidebarWidth() {
  const viewportMax = Math.floor(window.innerWidth * 0.5);
  const target = Math.round(window.innerWidth * 0.25);
  const max = Math.max(TASK_SB_MIN, Math.min(TASK_SB_MAX_ABS, viewportMax));
  return Math.min(max, Math.max(TASK_SB_MIN, target));
}

function applyTaskSidebarWidth(px) {
  const sb = document.getElementById('taskSidebar');
  if (!sb) return;
  const w = clampTaskSidebarWidth(px);
  taskSbStoredWidth = w;
  sb.style.setProperty('--task-sidebar-width', w + 'px');
  sb.style.width = w + 'px';
  sb.style.flexBasis = w + 'px';
}

function setTaskSidebarWidth(px) {
  applyTaskSidebarWidth(px);
}

function loadTaskSidebarWidth() {
  const saved = Number(localStorage.getItem('taskSidebarWidth'));
  taskSbStoredWidth = Number.isFinite(saved) && saved > 0
    ? clampTaskSidebarWidth(saved)
    : defaultTaskSidebarWidth();
  applyTaskSidebarWidth(taskSbStoredWidth);
}

function initTaskSidebarResize() {
  const sb = document.getElementById('taskSidebar');
  const handle = document.getElementById('taskResizeHandle');
  if (!sb || !handle || handle.dataset.resizeReady) return;
  handle.dataset.resizeReady = '1';

  let isResizing = false;
  let startX = 0;
  let startW = 0;

  function isNearSidebarLeftEdge(e) {
    const rect = sb.getBoundingClientRect();
    return e.clientX >= rect.left - 10 && e.clientX <= rect.left + 18;
  }

  function beginResize(e) {
    if (isResizing) return;
    if (e.button !== undefined && e.button !== 0) return;
    if (sb.classList.contains('hidden')) return;
    e.preventDefault();
    e.stopPropagation();
    isResizing = true;
    sb.classList.remove('toggling');
    startX = e.clientX;
    startW = sb.getBoundingClientRect().width || taskSbStoredWidth || defaultTaskSidebarWidth();
    document.body.classList.add('resizing-task-sb');
    sb.classList.add('resizing');
    if (handle.setPointerCapture && e.pointerId !== undefined) {
      try { handle.setPointerCapture(e.pointerId); } catch {}
    }
  }

  function moveResize(e) {
    if (!isResizing) {
      sb.classList.toggle('resize-edge-hover', !sb.classList.contains('hidden') && isNearSidebarLeftEdge(e));
      return;
    }
    e.preventDefault();
    const delta = startX - e.clientX;
    setTaskSidebarWidth(startW + delta);
  }

  function endResize(e) {
    if (!isResizing) return;
    isResizing = false;
    document.body.classList.remove('resizing-task-sb');
    sb.classList.remove('resizing', 'resize-edge-hover');
    localStorage.setItem('taskSidebarWidth', String(taskSbStoredWidth));
    if (handle.releasePointerCapture && e && e.pointerId !== undefined) {
      try { handle.releasePointerCapture(e.pointerId); } catch {}
    }
  }

  handle.addEventListener('pointerdown', beginResize);
  sb.addEventListener('pointerdown', e => { if (isNearSidebarLeftEdge(e)) beginResize(e); }, true);
  document.addEventListener('pointermove', moveResize);
  document.addEventListener('pointerup', endResize);
  document.addEventListener('pointercancel', endResize);

  handle.addEventListener('mousedown', beginResize);
  sb.addEventListener('mousedown', e => { if (isNearSidebarLeftEdge(e)) beginResize(e); }, true);
  document.addEventListener('mousemove', moveResize);
  document.addEventListener('mouseup', endResize);

  handle.addEventListener('dblclick', () => {
    setTaskSidebarWidth(defaultTaskSidebarWidth());
    localStorage.setItem('taskSidebarWidth', String(taskSbStoredWidth));
  });

  window.addEventListener('resize', () => {
    setTaskSidebarWidth(taskSbStoredWidth);
    if (!sb.classList.contains('hidden')) {
      localStorage.setItem('taskSidebarWidth', String(taskSbStoredWidth));
    }
    updateFolderGuide();
  });
}

function toggleTaskSidebar() {
  const sb      = document.getElementById('taskSidebar');
  const btn     = document.getElementById('taskToggleBtn');
  const opening = sb.classList.contains('hidden');

  if (opening) applyTaskSidebarWidth(taskSbStoredWidth || defaultTaskSidebarWidth());

  sb.classList.add('toggling');
  sb.addEventListener('transitionend', () => sb.classList.remove('toggling'), {once:true});
  sb.classList.toggle('hidden');
  btn.classList.toggle('active', opening);
  closeTaskMenu();
}

// ── Load tasks ────────────────────────────────────────────────────
async function loadTasks() {
  try {
    const r = await fetch('/api/tasks');
    taskState = await r.json();
  } catch { taskState = {activeTaskId:null, tasks:[]}; }
  renderTaskSidebar();
}

// ── Render sidebar ────────────────────────────────────────────────
function renderTaskSidebar() {
  const sel   = document.getElementById('taskSelect');
  const list  = document.getElementById('taskList');
  const empty = document.getElementById('taskEmpty');
  const count = document.getElementById('taskCount');
  const pcBtn = document.getElementById('playCurrentBtn');
  const pnBtn = document.getElementById('playNextBtn');
  const mBtn  = document.getElementById('taskMenuBtn');

  // Populate select
  sel.innerHTML = taskState.tasks.length === 0
    ? '<option value="">（無任務）</option>'
    : taskState.tasks.map(t =>
        `<option value="${t.id}" ${t.id===taskState.activeTaskId?'selected':''}>${escHtml(t.name)} (${t.items.length})</option>`
      ).join('');

  const task = activeTask();
  mBtn.disabled = !task;

  if (!task) {
    list.innerHTML = '';
    list.appendChild(empty);
    empty.textContent = '點「＋」建立第一個任務';
    count.textContent = '0 項';
    pcBtn.disabled = pnBtn.disabled = true;
    return;
  }

  const items = task.items;
  count.textContent = `${items.length} 項`;
  pcBtn.disabled = items.length === 0;
  pnBtn.disabled = items.length === 0;

  if (items.length === 0) {
    list.innerHTML = '';
    empty.className = 'task-empty';
    empty.textContent = '拖曳左側媒體卡片到此處加入清單';
    list.appendChild(empty);
    return;
  }

  const nextIndex = getNextTaskIndex(task);
  list.innerHTML = items
    .map((item, i) => renderTaskItemCompact(item, i, task.currentIndex, nextIndex))
    .join('');
}

// ── Task CRUD ─────────────────────────────────────────────────────
async function promptCreateTask() {
  const name = prompt('新任務名稱：');
  if (!name || !name.trim()) return;
  try {
    const r = await fetch('/api/tasks/create', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name: name.trim()})
    });
    const d = await r.json();
    if (d.ok) {
      taskState.tasks.push(d.task);
      taskState.activeTaskId = d.activeTaskId;
      renderTaskSidebar();
      // ensure sidebar is open
      const sb = document.getElementById('taskSidebar');
      if (sb.classList.contains('hidden')) toggleTaskSidebar();
    } else { toast(d.err || '建立失敗', 'err'); }
  } catch { toast('無法連線', 'err'); }
}

async function switchTask(id) {
  if (!id) return;
  closeTaskMenu();
  try {
    await fetch('/api/tasks/set-active', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id})
    });
    taskState.activeTaskId = id;
    renderTaskSidebar();
  } catch { toast('切換失敗', 'err'); }
}

async function promptRenameTask() {
  closeTaskMenu();
  const task = activeTask();
  if (!task) return;
  const name = prompt('新名稱：', task.name);
  if (!name || !name.trim() || name.trim() === task.name) return;
  try {
    const r = await fetch('/api/tasks/rename', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: task.id, name: name.trim()})
    });
    const d = await r.json();
    if (d.ok) { task.name = name.trim(); renderTaskSidebar(); }
    else { toast(d.err || '改名失敗', 'err'); }
  } catch { toast('無法連線', 'err'); }
}

async function confirmDeleteTask() {
  closeTaskMenu();
  const task = activeTask();
  if (!task) return;
  if (!confirm(`確定刪除「${task.name}」？\n清單內容將一併移除，檔案本身不受影響。`)) return;
  try {
    const r = await fetch('/api/tasks/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: task.id})
    });
    const d = await r.json();
    if (d.ok) {
      taskState.tasks = taskState.tasks.filter(t => t.id !== task.id);
      taskState.activeTaskId = d.activeTaskId;
      renderTaskSidebar();
    } else { toast(d.err || '刪除失敗', 'err'); }
  } catch { toast('無法連線', 'err'); }
}

// ── Task item operations ──────────────────────────────────────────
function hasDragType(e, type) {
  return e.dataTransfer && Array.from(e.dataTransfer.types || []).includes(type);
}

function readMediaDragItem(e) {
  try {
    const raw = e.dataTransfer.getData(MEDIA_DRAG_TYPE);
    if (!raw) return null;
    const item = JSON.parse(raw);
    if (!item || !item.path) return null;
    return {
      path: item.path,
      name: item.name || item.path.split('\\').pop(),
      stem: item.stem || item.name || item.path,
      type: item.type || 'doc',
      ext: item.ext || ''
    };
  } catch {
    return null;
  }
}

function clearTaskDropState() {
  const list = document.getElementById('taskList');
  const empty = document.getElementById('taskEmpty');
  if (list) list.classList.remove('drop-over');
  if (empty) empty.classList.remove('drop-over');
  document.querySelectorAll('.task-item.drag-over-top,.task-item.drag-over-bot')
    .forEach(el => el.classList.remove('drag-over-top','drag-over-bot'));
}

async function addItemToActiveTask(item, index=null) {
  const task = activeTask();
  if (!task) {
    toast('請先建立或選擇任務', 'err');
    return;
  }
  const items = [...task.items];
  const insertAt = Number.isInteger(index)
    ? Math.max(0, Math.min(index, items.length))
    : items.length;
  items.splice(insertAt, 0, item);
  await saveItems(items);
  toast('已加入：' + (item.stem || item.name), 'ok');
}

function startTaskItemDrag(e, index) {
  draggingTaskIndex = index;
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData(TASK_DRAG_TYPE, String(index));
  e.currentTarget.classList.add('dragging');
}

function overTaskItem(e, index) {
  if (!hasDragType(e, TASK_DRAG_TYPE) && !hasDragType(e, MEDIA_DRAG_TYPE)) return;
  e.preventDefault();
  e.stopPropagation();
  e.dataTransfer.dropEffect = hasDragType(e, MEDIA_DRAG_TYPE) ? 'copy' : 'move';

  document.querySelectorAll('.task-item.drag-over-top,.task-item.drag-over-bot')
    .forEach(el => el.classList.remove('drag-over-top','drag-over-bot'));
  const rect = e.currentTarget.getBoundingClientRect();
  const after = e.clientY > rect.top + rect.height / 2;
  e.currentTarget.classList.add(after ? 'drag-over-bot' : 'drag-over-top');
}

async function dropOnTaskItem(e, index) {
  if (!hasDragType(e, TASK_DRAG_TYPE) && !hasDragType(e, MEDIA_DRAG_TYPE)) return;
  e.preventDefault();
  e.stopPropagation();
  const rect = e.currentTarget.getBoundingClientRect();
  const after = e.clientY > rect.top + rect.height / 2;
  const targetIndex = index + (after ? 1 : 0);
  clearTaskDropState();

  if (hasDragType(e, MEDIA_DRAG_TYPE)) {
    const item = readMediaDragItem(e);
    if (item) await addItemToActiveTask(item, targetIndex);
    return;
  }

  const from = Number(e.dataTransfer.getData(TASK_DRAG_TYPE));
  await moveTaskItem(from, targetIndex);
}

function endTaskItemDrag() {
  draggingTaskIndex = null;
  document.querySelectorAll('.task-item.dragging')
    .forEach(el => el.classList.remove('dragging'));
  clearTaskDropState();
}

async function moveTaskItem(from, rawTo) {
  const task = activeTask();
  if (!task || !Number.isInteger(from) || from < 0 || from >= task.items.length) return;
  let to = Math.max(0, Math.min(rawTo, task.items.length));
  if (from < to) to -= 1;
  if (from === to) return;

  const items = [...task.items];
  const [moved] = items.splice(from, 1);
  items.splice(to, 0, moved);
  if (task.currentIndex === from) task.currentIndex = to;
  else if (task.currentIndex > from && task.currentIndex <= to) task.currentIndex -= 1;
  else if (task.currentIndex < from && task.currentIndex >= to) task.currentIndex += 1;
  await saveItems(items);
}
async function saveItems(items) {
  const task = activeTask();
  if (!task) return;
  task.items = items;
  try {
    await fetch('/api/tasks/save-items', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: task.id, items})
    });
    await fetch('/api/tasks/set-current', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: task.id, index: task.currentIndex})
    });
  } catch { toast('儲存失敗', 'err'); }
  renderTaskSidebar();
}

async function playTaskItem(index) {
  const task = activeTask();
  if (!task || index < 0 || index >= task.items.length) return;
  const item = task.items[index];
  try {
    const r = await fetch('/api/open?path=' + encodeURIComponent(item.path));
    const d = await r.json();
    if (!d.ok) { toast('開啟失敗: ' + (d.err||''), 'err'); return; }
    toast('已開啟 ' + (item.stem||item.name), 'ok');
  } catch { toast('無法連線', 'err'); return; }
  task.currentIndex = index;
  try {
    await fetch('/api/tasks/set-current', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id: task.id, index})
    });
  } catch {}
  renderTaskSidebar();
}

function playCurrentItem() {
  const task = activeTask();
  if (!task) return;
  const idx = task.currentIndex < 0 ? 0 : task.currentIndex;
  playTaskItem(idx);
}

function playNextItem() {
  const task = activeTask();
  if (!task || !task.items.length) return;
  const next = (task.currentIndex + 1) % task.items.length;
  playTaskItem(next);
}

async function removeTaskItem(e, index) {
  e.stopPropagation();
  const task = activeTask();
  if (!task) return;
  const items = task.items.filter((_, i) => i !== index);
  if (task.currentIndex >= items.length) task.currentIndex = items.length - 1;
  await saveItems(items);
}

// ── Task menu ─────────────────────────────────────────────────────
function toggleTaskMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('taskMenu');
  const btn = document.getElementById('taskMenuBtn');
  if (btn && btn.disabled) return;
  menu.classList.toggle('hidden');
}
function closeTaskMenu() {
  const menu = document.getElementById('taskMenu');
  if (menu) menu.classList.add('hidden');
}
document.addEventListener('click', e => {
  if (!e.target.closest('.task-menu-wrap')) closeTaskMenu();
  if (!e.target.closest('.kcard-group-more-wrap')) closeKcGroupPopup();
});
document.addEventListener('fullscreenchange', () => {
  const btn = document.getElementById('kcFullscreenBtn');
  const player = document.getElementById('kcPlayer');
  if (btn) btn.textContent = document.fullscreenElement === player ? '離開全螢幕' : '全螢幕';
  showKcPlayerControls();
});

// ── Toast ─────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, type='') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (type ? ' '+type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
}

// ── Utils ─────────────────────────────────────────────────────────
function fmtSize(b) {
  if(b<1024) return b+' B';
  if(b<1048576) return (b/1024).toFixed(1)+' KB';
  if(b<1073741824) return (b/1048576).toFixed(1)+' MB';
  return (b/1073741824).toFixed(2)+' GB';
}
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function esc(s) { return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'"); }

// ── Card Mode ─────────────────────────────────────────────────────
let cardModeActive  = localStorage.getItem('cardModeActive') !== '0';
let kcGroups        = [];   // full card_groups array
let kcActiveGroupId = '';   // active group id
// Projection of active group (all existing card functions use these three)
let kcData         = [];
let kcCount        = 6;
let kcBackground   = '';
let kcBgPicking    = false;
let kcEditIndex    = -1;
let kcEditTmp      = {};
let kcPlayingIndex = -1;
let kcPlayerControlsTimer = null;
let kcGroupDeleteMode = false;
let kcDeleteSelectedIds = new Set();
const KC_THUMB_POSITIONS = [
  ['left top', '↖'], ['center top', '↑'], ['right top', '↗'],
  ['left center', '←'], ['center center', '•'], ['right center', '→'],
  ['left bottom', '↙'], ['center bottom', '↓'], ['right bottom', '↘']
];

function newKcGroupId() {
  return 'g_' + Math.random().toString(36).slice(2, 10).padEnd(8, '0');
}

function defaultKcGroup(name) {
  return {
    id:              newKcGroupId(),
    name:            (name || '群組 1').slice(0, 30),
    card_count:      6,
    card_background: '',
    cards:           []
  };
}

function activeKcGroup() {
  return kcGroups.find(g => g.id === kcActiveGroupId) || kcGroups[0] || null;
}

function ensureKcGroups() {
  if (!kcGroups || !kcGroups.length) {
    const g = defaultKcGroup('群組 1');
    g.id = 'g_default';
    kcGroups = [g];
  }
  const ids = new Set(kcGroups.map(g => g.id));
  if (!kcActiveGroupId || !ids.has(kcActiveGroupId)) {
    kcActiveGroupId = kcGroups[0].id;
  }
}

// Write projection variables (kcData/kcCount/kcBackground) into active group object
function writeActiveKcProjection() {
  const g = activeKcGroup();
  if (!g) return;
  g.card_count      = kcCount;
  g.card_background = kcBackground;
  g.cards           = kcData;
}

// Sync projection variables from active group
function syncActiveKcProjection() {
  const g = activeKcGroup();
  if (!g) return;
  kcCount      = g.card_count      || 6;
  kcBackground = g.card_background || '';
  kcData       = Array.isArray(g.cards) ? g.cards : [];
  syncKcData();
}

async function loadCards() {
  try {
    const r = await fetch('/api/cards');
    const d = await r.json();
    if (Array.isArray(d.card_groups) && d.card_groups.length) {
      kcGroups        = d.card_groups;
      kcActiveGroupId = d.card_active_group_id || '';
    } else {
      // Fallback for old-format response
      kcGroups = [{
        id:              'g_default',
        name:            '群組 1',
        card_count:      d.card_count || 6,
        card_background: d.card_background || '',
        cards:           d.cards || []
      }];
      kcActiveGroupId = 'g_default';
    }
    ensureKcGroups();
    syncActiveKcProjection();
  } catch {}
}

function syncKcData() {
  while (kcData.length < kcCount) {
    kcData.push({id: kcData.length, title:'', file:'', thumbnail:'', thumb_position:'center center'});
  }
}

function normalizeKcThumbPosition(pos) {
  const value = String(pos || 'center center').trim().toLowerCase();
  return KC_THUMB_POSITIONS.some(p => p[0] === value) ? value : 'center center';
}

function thumbPositionStyle(pos) {
  return '--thumb-pos:' + normalizeKcThumbPosition(pos);
}

async function saveKcCards() {
  writeActiveKcProjection();
  try {
    await fetch('/api/cards/save', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({
        card_groups:          kcGroups,
        card_active_group_id: kcActiveGroupId
      })
    });
  } catch { toast('卡片設定儲存失敗', 'err'); }
}

function toggleCardMode() {
  cardModeActive = !cardModeActive;
  localStorage.setItem('cardModeActive', cardModeActive ? '1' : '0');
  document.getElementById('cardModeBtn').classList.toggle('active', cardModeActive);
  if (cardModeActive) {
    renderCardMode();
  } else {
    closeKCardPlayer();
    renderTopbarCardGroups();
    const ga = document.getElementById('gridArea');
    ga.style.backgroundImage = ga.style.backgroundSize = ga.style.backgroundPosition = '';
    filterRender();
  }
}

function closeKcGroupPopup() {
  const pop = document.getElementById('kcardGroupPopover');
  if (pop) pop.classList.add('hidden');
  if (kcGroupDeleteMode) {
    kcGroupDeleteMode = false;
    kcDeleteSelectedIds.clear();
    renderTopbarCardGroups();
  }
}

function positionKcGroupPopover(btn) {
  const pop = document.getElementById('kcardGroupPopover');
  if (!pop || !btn) return;
  const rect = btn.getBoundingClientRect();
  const left = Math.max(12, Math.min(window.innerWidth - 292, rect.left));
  pop.style.setProperty('--kc-pop-left', left + 'px');
  pop.style.setProperty('--kc-pop-top', (rect.bottom + 14) + 'px');
}

function reopenKcGroupPopup() {
  renderTopbarCardGroups();
  const btn = document.querySelector('#topbarCardGroups .kcard-group-more');
  const pop = document.getElementById('kcardGroupPopover');
  positionKcGroupPopover(btn);
  if (pop) pop.classList.remove('hidden');
}

function toggleKcGroupPopup(e) {
  if (e) e.stopPropagation();
  const pop = document.getElementById('kcardGroupPopover');
  if (!pop) return;
  const btn = e && e.currentTarget ? e.currentTarget : null;
  positionKcGroupPopover(btn);
  pop.classList.toggle('hidden');
}

function renderTopbarCardGroups() {
  const host = document.getElementById('topbarCardGroups');
  if (!host) return;
  if (!cardModeActive) {
    host.classList.add('hidden');
    host.innerHTML = '';
    return;
  }
  ensureKcGroups();
  const active = activeKcGroup();
  const tabsHtml = kcGroups.map(g => {
    const isActive = g.id === kcActiveGroupId;
    const safeId   = g.id.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    return '<button class="kcard-group-tab' + (isActive ? ' active' : '') +
      '" onclick="setActiveKcGroup(\'' + safeId + '\')">' +
      escHtml(g.name) + '</button>';
  }).join('');

  const bgLabel = kcBackground ? '更換背景' : '設定背景';
  const ids = new Set(kcGroups.map(g => g.id));
  kcDeleteSelectedIds = new Set([...kcDeleteSelectedIds].filter(id => ids.has(id)));
  const deleteRows = kcGroups.map(g => {
    const safeId = esc(g.id);
    const checked = kcDeleteSelectedIds.has(g.id) ? ' checked' : '';
    const activeMark = g.id === kcActiveGroupId ? '目前' : '';
    return '<label class="kcard-delete-choice' + (activeMark ? ' active' : '') + '">' +
      '<input type="checkbox" onchange="toggleKcDeleteSelection(\'' + safeId + '\', this.checked)"' + checked + '>' +
      '<span>' + escHtml(g.name) + '</span>' +
      (activeMark ? '<small>' + activeMark + '</small>' : '') +
    '</label>';
  }).join('');
  const deletePanel = kcGroupDeleteMode
    ? '<div class="kcard-delete-panel">' +
        '<div class="kcard-delete-help">勾選不要的群組後一次刪除。系統會至少保留一個群組。</div>' +
        '<div class="kcard-delete-list">' + deleteRows + '</div>' +
        '<div class="kcard-delete-footer">' +
          '<button class="kcard-pop-small" onclick="cancelKcGroupMultiDelete()">取消</button>' +
          '<button class="kcard-pop-small danger" onclick="deleteSelectedKcGroups()">刪除勾選</button>' +
        '</div>' +
      '</div>'
    : '';
  host.innerHTML =
    '<div class="kcard-group-tabs">' + tabsHtml + '</div>' +
    '<div class="topbar-card-actions">' +
      '<button class="kcard-group-add" onclick="createKcGroup()" title="新增群組">＋</button>' +
      '<div class="kcard-group-more-wrap">' +
        '<button class="kcard-group-more" onclick="toggleKcGroupPopup(event)" title="群組設定">⋯</button>' +
        '<div class="kcard-group-popover hidden" id="kcardGroupPopover" onclick="event.stopPropagation()">' +
          '<div class="kcard-pop-title">' + escHtml(active ? active.name : '群組') + '</div>' +
          '<div class="kcard-pop-row">' +
            '<span class="kcard-pop-label">卡片數量</span>' +
            '<div class="kcard-pop-actions">' +
              '<button class="kcard-count-btn" onclick="adjustKcCount(-1)">−</button>' +
              '<span class="kcard-pop-count">' + kcCount + '</span>' +
              '<button class="kcard-count-btn" onclick="adjustKcCount(1)">＋</button>' +
            '</div>' +
          '</div>' +
          '<div class="kcard-pop-row">' +
            '<span class="kcard-pop-label">背景</span>' +
            '<div class="kcard-pop-actions">' +
              '<button class="kcard-pop-small" onclick="kcSetBackground()">' + bgLabel + '</button>' +
              (kcBackground ? '<button class="kcard-pop-small" onclick="kcClearBackground()">清除</button>' : '') +
            '</div>' +
          '</div>' +
          '<div class="kcard-pop-row">' +
            '<span class="kcard-pop-label">群組</span>' +
            '<div class="kcard-pop-actions">' +
              '<button class="kcard-pop-small" onclick="renameActiveKcGroup()">改名</button>' +
              '<button class="kcard-pop-small danger" onclick="deleteActiveKcGroup()">刪除</button>' +
              '<button class="kcard-pop-small danger" onclick="showKcGroupMultiDelete()">多選刪除</button>' +
            '</div>' +
          '</div>' +
          deletePanel +
        '</div>' +
      '</div>' +
    '</div>';
  host.classList.remove('hidden');
}

function scrollKcGroupsToEnd() {
  requestAnimationFrame(() => {
    const tabs = document.querySelector('#topbarCardGroups .kcard-group-tabs');
    if (tabs) tabs.scrollLeft = tabs.scrollWidth;
  });
}

function renderCardMode() {
  ensureKcGroups();
  syncKcData();
  renderTopbarCardGroups();

  // ── Cards ─────────────────────────────────────────────────────────
  syncKcData();
  const cards = kcData.slice(0, kcCount).map((card, i) => {
    const hasFile  = !!card.file;
    const hasThumb = !!card.thumbnail;
    const stem = hasFile ? card.file.replace(/.*[\\\/]/, '').replace(/\.[^.]+$/, '') : '';
    const displayTitle = (card.title || stem) || ('卡片 ' + (i + 1));
    const hasVisual = hasThumb || hasFile;
    const cls = 'kcard' + (hasVisual ? ' kcard-has-visual' : ' kcard-empty');
    const thumbStyle = thumbPositionStyle(card.thumb_position);

    let thumbHtml = '';
    if (hasThumb) {
      thumbHtml = '<div class="kcard-thumb-wrap"><img src="/api/card-image?path=' + encodeURIComponent(card.thumbnail) + '" alt="" style="' + thumbStyle + '" onerror="this.parentElement.style.display=\'none\'"></div><div class="kcard-overlay"></div>';
    } else if (hasFile) {
      const entry = fileMap.get(card.file);
      let src = '';
      if (entry && entry.thumb)        src = '/api/thumb?key=' + encodeURIComponent(entry.thumb);
      else if (entry && entry.img_url) src = entry.img_url;
      else                             src = '/api/file-thumb?path=' + encodeURIComponent(card.file);
      thumbHtml = '<div class="kcard-thumb-wrap"><img src="' + src + '" alt="" style="' + thumbStyle + '" onerror="this.parentElement.style.display=\'none\'"></div><div class="kcard-overlay"></div>';
    }

    const emptyHtml = !hasVisual
      ? '<div class="kcard-empty-center"><div class="kcard-empty-icon">' + (i+1) + '</div><div class="kcard-empty-hint">點擊 ✏ 設定</div></div>'
      : '';
    const filenameHtml = hasFile
      ? '<div class="kcard-file">' + escHtml(card.file.replace(/.*[\\\/]/, '')) + '</div>'
      : '';

    return '<div class="' + cls + '" onclick="openKCard(' + i + ')">' +
      thumbHtml + emptyHtml +
      '<div class="kcard-footer">' +
        '<div class="kcard-title">' + escHtml(displayTitle) + '</div>' +
        filenameHtml +
      '</div>' +
      '<button class="kcard-edit-btn" onclick="editKCard(event,' + i + ')" title="編輯卡片">✏</button>' +
    '</div>';
  }).join('');

  // ── Render ────────────────────────────────────────────────────────
  const gridArea = document.getElementById('gridArea');
  gridArea.innerHTML =
    '<div class="kcard-view">' +
      '<div class="kcard-scroll"><div class="kcard-grid">' + cards + '</div></div>' +
    '</div>';

  if (kcBackground) {
    gridArea.style.backgroundImage    = 'url(\'/api/card-image?path=' + encodeURIComponent(kcBackground) + '\')';
    gridArea.style.backgroundSize     = 'cover';
    gridArea.style.backgroundPosition = 'center';
  } else {
    gridArea.style.backgroundImage = gridArea.style.backgroundSize = gridArea.style.backgroundPosition = '';
  }
}

// ── Group operations ─────────────────────────────────────────────
function nextKcGroupName() {
  const names = new Set(kcGroups.map(g => g.name));
  let n = kcGroups.length + 1;
  while (names.has('群組 ' + n)) n++;
  return '群組 ' + n;
}

async function setActiveKcGroup(id) {
  if (id === kcActiveGroupId) return;
  closeKCardPlayer();
  closeKcModal();  // discard any open edit modal before switching
  writeActiveKcProjection();
  kcActiveGroupId = id;
  ensureKcGroups();
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
}

async function createKcGroup() {
  writeActiveKcProjection();
  const g = defaultKcGroup(nextKcGroupName());
  kcGroups.push(g);
  kcActiveGroupId = g.id;
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
  scrollKcGroupsToEnd();
  toast('已新增「' + g.name + '」', 'ok');
}

async function renameActiveKcGroup() {
  const g = activeKcGroup();
  if (!g) return;
  const name = prompt('群組名稱（最多 30 字）', g.name);
  if (name === null) return;
  const trimmed = name.trim().slice(0, 30);
  if (!trimmed) { toast('名稱不可為空', 'err'); return; }
  g.name = trimmed;
  await saveKcCards();
  renderCardMode();
}

function showKcGroupMultiDelete() {
  kcGroupDeleteMode = true;
  kcDeleteSelectedIds.clear();
  reopenKcGroupPopup();
}

function cancelKcGroupMultiDelete() {
  kcGroupDeleteMode = false;
  kcDeleteSelectedIds.clear();
  reopenKcGroupPopup();
}

function toggleKcDeleteSelection(id, checked) {
  if (checked) kcDeleteSelectedIds.add(id);
  else kcDeleteSelectedIds.delete(id);
}

async function deleteSelectedKcGroups() {
  const selected = kcGroups.filter(g => kcDeleteSelectedIds.has(g.id));
  if (!selected.length) { toast('請先勾選要刪除的群組', 'err'); return; }
  if (selected.length >= kcGroups.length) {
    toast('至少需要保留一個群組', 'err');
    return;
  }
  const names = selected.map(g => g.name).join('、');
  if (!confirm('刪除 ' + selected.length + ' 個群組？\n' + names + '\n\n這些群組的卡片設定會一併移除。')) return;

  writeActiveKcProjection();
  const selectedIds = new Set(selected.map(g => g.id));
  kcGroups = kcGroups.filter(g => !selectedIds.has(g.id));
  if (selectedIds.has(kcActiveGroupId) || !kcGroups.some(g => g.id === kcActiveGroupId)) {
    kcActiveGroupId = kcGroups[0].id;
  }
  kcGroupDeleteMode = false;
  kcDeleteSelectedIds.clear();
  ensureKcGroups();
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
  toast('已刪除 ' + selected.length + ' 個群組', 'ok');
}

async function deleteActiveKcGroup() {
  if (kcGroups.length <= 1) { toast('至少需要保留一個群組', 'err'); return; }
  const g = activeKcGroup();
  if (!g) return;
  if (!confirm('刪除「' + g.name + '」？此群組的所有卡片設定將一併移除。')) return;
  const idx = kcGroups.indexOf(g);
  kcGroups.splice(idx, 1);
  kcActiveGroupId = kcGroups[Math.max(0, idx - 1)].id;
  syncActiveKcProjection();
  await saveKcCards();
  renderCardMode();
}

async function adjustKcCount(delta) {
  const n = Math.max(1, Math.min(24, kcCount + delta));
  if (n === kcCount) return;
  kcCount = n;
  syncKcData();
  await saveKcCards();
  renderCardMode();
}

function openKCard(i) {
  const card = kcData[i];
  if (!card || !card.file) { toast('此卡片尚未設定播放檔案，請點 ✏ 設定', 'err'); return; }
  const kind = kcardPlayableKind(card.file);
  if (!kind || kind === 'external') {
    openFile(card.file);
    return;
  }
  showKCardPlayer(i);
}

function kcardExt(path) {
  const m = String(path || '').toLowerCase().match(/\.([^.\\\/]+)$/);
  return m ? m[1] : '';
}

function kcardPlayableKind(path) {
  const ext = kcardExt(path);
  if (['jpg','jpeg','png','gif','bmp','webp','svg','tiff','tif','heic','avif'].includes(ext)) return 'image';
  if (['mp4','webm','mov','m4v'].includes(ext)) return 'video';
  if (['mp3','wav','flac','aac','ogg','m4a','opus'].includes(ext)) return 'audio';
  if (ext === 'pdf') return 'pdf';
  return 'external';
}

function kcardDisplayName(card) {
  const fileName = card && card.file ? card.file.replace(/.*[\\\/]/, '') : '';
  return (card && card.title) || fileName || '未命名卡片';
}

function kcardMediaUrl(path) {
  return '/api/media?path=' + encodeURIComponent(path);
}

function showKCardPlayer(index) {
  const card = kcData[index];
  if (!card || !card.file) return;
  const kind = kcardPlayableKind(card.file);
  if (!kind || kind === 'external') { openFile(card.file); return; }

  kcPlayingIndex = index;
  const player = document.getElementById('kcPlayer');
  const stage  = document.getElementById('kcPlayerStage');
  const title  = document.getElementById('kcPlayerTitle');
  const url    = kcardMediaUrl(card.file);
  title.textContent = kcardDisplayName(card);

  if (kind === 'image') {
    stage.innerHTML = '<img src="' + url + '" alt="">';
  } else if (kind === 'video') {
    stage.innerHTML = '<video src="' + url + '" controls autoplay playsinline></video>';
  } else if (kind === 'audio') {
    stage.innerHTML =
      '<div class="kc-player-audio">' +
        '<div class="kc-player-audio-icon">♪</div>' +
        '<div>' + escHtml(kcardDisplayName(card)) + '</div>' +
        '<audio src="' + url + '" controls autoplay></audio>' +
      '</div>';
  } else if (kind === 'pdf') {
    stage.innerHTML = '<iframe src="' + url + '"></iframe>';
  }
  player.classList.remove('hidden');
  showKcPlayerControls();
}

function closeKCardPlayer() {
  const player = document.getElementById('kcPlayer');
  const stage  = document.getElementById('kcPlayerStage');
  if (document.fullscreenElement === player && document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  }
  if (stage) stage.innerHTML = '';
  if (player) player.classList.add('hidden');
}

function showKcPlayerControls() {
  const player = document.getElementById('kcPlayer');
  if (!player || player.classList.contains('hidden')) return;
  player.classList.add('controls-visible');
  clearTimeout(kcPlayerControlsTimer);
  kcPlayerControlsTimer = setTimeout(() => {
    player.classList.remove('controls-visible');
  }, 1800);
}

function toggleKCardFullscreen() {
  const player = document.getElementById('kcPlayer');
  if (!player) return;
  if (document.fullscreenElement === player) {
    document.exitFullscreen && document.exitFullscreen();
  } else if (player.requestFullscreen) {
    player.requestFullscreen().then(showKcPlayerControls).catch(() => toast('無法進入全螢幕', 'err'));
  }
}

function handleKcPlayerBackdropClick(e) {
  if (e.target.closest('.kc-player-bar,.kc-player-nav')) return;
  if (e.target.closest('img,video,audio,iframe,.kc-player-audio')) return;
  closeKCardPlayer();
}

function findAdjacentPlayableKCard(from, dir) {
  const len = kcData.length;
  if (!len) return -1;
  for (let step = 1; step <= len; step++) {
    const idx = (from + dir * step + len) % len;
    const card = kcData[idx];
    if (card && card.file) return idx;
  }
  return -1;
}

function playAdjacentKCard(dir) {
  const start = kcPlayingIndex >= 0 ? kcPlayingIndex : 0;
  const next = findAdjacentPlayableKCard(start, dir);
  if (next < 0) { toast('此群組沒有可播放的卡片', 'err'); return; }
  openKCard(next);
}

function openCurrentKCardExternal() {
  const card = kcData[kcPlayingIndex];
  if (!card || !card.file) { toast('目前沒有播放中的卡片', 'err'); return; }
  openFile(card.file);
}

function editKCard(e, i) {
  e.stopPropagation();
  kcEditIndex = i;
  const card = kcData[i] || {};
  kcEditTmp = {
    title: card.title || '',
    file: card.file || '',
    thumbnail: card.thumbnail || '',
    thumb_position: normalizeKcThumbPosition(card.thumb_position)
  };
  document.getElementById('kcEdit-title').value = kcEditTmp.title;
  document.getElementById('kcEdit-file').value  = kcEditTmp.file;
  document.getElementById('kcEdit-thumb').value = kcEditTmp.thumbnail;
  document.getElementById('kcModalTitle').textContent = '編輯卡片 ' + (i + 1);
  renderKcThumbPositionControls();
  kcUpdatePreview('thumb', kcEditTmp.thumbnail);
  document.getElementById('kcModal').classList.remove('hidden');
}

function renderKcThumbPositionControls() {
  const grid = document.getElementById('kcThumbPositionGrid');
  if (!grid) return;
  const active = normalizeKcThumbPosition(kcEditTmp.thumb_position);
  grid.innerHTML = KC_THUMB_POSITIONS.map(([pos, label]) =>
    '<button class="kc-position-btn' + (pos === active ? ' active' : '') +
    '" onclick="setKcThumbPosition(\'' + pos + '\')" title="' + pos + '">' +
    label + '</button>'
  ).join('');
}

function setKcThumbPosition(pos) {
  kcEditTmp.thumb_position = normalizeKcThumbPosition(pos);
  renderKcThumbPositionControls();
  const img = document.getElementById('kcPrev-thumb');
  if (img) img.style.setProperty('--thumb-pos', kcEditTmp.thumb_position);
}

function kcUpdatePreview(type, path) {
  const img = document.getElementById('kcPrev-' + type);
  if (!img) return;
  if (type === 'thumb') img.style.setProperty('--thumb-pos', normalizeKcThumbPosition(kcEditTmp.thumb_position));
  if (path) {
    img.src = '/api/card-image?path=' + encodeURIComponent(path);
    img.onload  = () => img.classList.add('show');
    img.onerror = () => img.classList.remove('show');
  } else {
    img.classList.remove('show');
    img.src = '';
  }
}

async function kcBrowse(btn, field) {
  const origText = btn.textContent;
  btn.disabled = true; btn.textContent = '⏳';
  const mode = (field === 'thumbnail' || field === 'background') ? 'image' : 'any';
  try {
    const r = await fetch('/api/browse-file?mode=' + mode);
    const d = await r.json();
    if (d.ok && d.path) {
      kcEditTmp[field] = d.path;
      if (field === 'file') {
        document.getElementById('kcEdit-file').value = d.path;
      } else if (field === 'thumbnail') {
        document.getElementById('kcEdit-thumb').value = d.path;
        kcUpdatePreview('thumb', d.path);
      } else if (field === 'background') {
        document.getElementById('kcEdit-bg').value = d.path;
        kcUpdatePreview('bg', d.path);
      }
    }
  } catch { toast('無法開啟選擇視窗', 'err'); }
  btn.disabled = false; btn.textContent = origText;
}

function kcClearField(field) {
  kcEditTmp[field] = '';
  if (field === 'file') {
    document.getElementById('kcEdit-file').value = '';
  } else if (field === 'thumbnail') {
    document.getElementById('kcEdit-thumb').value = '';
    kcUpdatePreview('thumb', '');
  } else if (field === 'background') {
    document.getElementById('kcEdit-bg').value = '';
    kcUpdatePreview('bg', '');
  }
}

function closeKcModal() {
  document.getElementById('kcModal').classList.add('hidden');
  kcEditIndex = -1; kcEditTmp = {};
}

async function saveKcCard() {
  if (kcEditIndex < 0) return;
  while (kcData.length <= kcEditIndex) {
    kcData.push({id: kcData.length, title:'', file:'', thumbnail:'', thumb_position:'center center'});
  }
  kcData[kcEditIndex] = {
    id:             kcEditIndex,
    title:          document.getElementById('kcEdit-title').value.trim(),
    file:           kcEditTmp.file      || '',
    thumbnail:      kcEditTmp.thumbnail || '',
    thumb_position: normalizeKcThumbPosition(kcEditTmp.thumb_position)
  };
  await saveKcCards();
  closeKcModal();
  renderCardMode();
  toast('卡片已儲存', 'ok');
}

async function kcSetBackground() {
  if (kcBgPicking) return;
  kcBgPicking = true;
  try {
    const r = await fetch('/api/browse-file?mode=image');
    const d = await r.json();
    if (d.ok && d.path) {
      kcBackground = d.path;
      await saveKcCards();
      renderCardMode();
    }
  } catch { toast('無法開啟選擇視窗', 'err'); }
  kcBgPicking = false;
}

async function kcClearBackground() {
  kcBackground = '';
  await saveKcCards();
  renderCardMode();
}

async function clearKcCard() {
  if (kcEditIndex < 0) return;
  if (!confirm('清除卡片 ' + (kcEditIndex + 1) + ' 的所有設定？')) return;
  kcData[kcEditIndex] = {id: kcEditIndex, title:'', file:'', thumbnail:'', thumb_position:'center center'};
  await saveKcCards();
  closeKcModal();
  renderCardMode();
  toast('已清除', 'ok');
}

init();
</script>
</body>
</html>
"""

# ── Main ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Reconfigure stdout/stderr to UTF-8 so emoji and CJK don't crash on
    # Windows consoles with non-UTF8 codepages (e.g. CP950 on zh-TW systems).
    for _stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(_stream, 'reconfigure'):
                _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    # ── Single-instance guard ─────────────────────────────────────────
    if port_in_use(PORT):
        print('已有媒體啟動器正在執行，已開啟現有視窗')
        webbrowser.open(f'http://localhost:{PORT}')
        sys.exit(0)

    # ── Init data dir & seed defaults ────────────────────────────────
    _init_data_dir()

    # ── Open browser once server is ready (poll, don't sleep) ────────
    def _open_when_ready():
        url = f'http://localhost:{PORT}/'
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                urllib.request.urlopen(url, timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        webbrowser.open(f'http://localhost:{PORT}')
    threading.Thread(target=_open_when_ready, daemon=True).start()

    print(f'╔══════════════════════════════╗')
    print(f'║  🎬  媒體啟動器已啟動        ║')
    print(f'║  http://localhost:{PORT}        ║')
    print(f'╚══════════════════════════════╝')
    print(f'資料目錄：{DATA_DIR}')
    print('按 Ctrl+C 停止')
    srv = http.server.ThreadingHTTPServer(('localhost', PORT), H)
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\n已停止')
