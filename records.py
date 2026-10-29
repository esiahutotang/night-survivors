"""Best runs in localStorage on web, or an atomic JSON file on desktop."""
import json
import sys
from pathlib import Path
from challenges import rank

STORAGE_KEY = 'night-survivors.records.v1'


def valid_result(value):
    if not isinstance(value, dict):
        return False
    for key in ('version', 'day', 'preset', 'mode'):
        if not isinstance(value.get(key), str) or len(value[key]) > 64:
            return False
    if value['mode'] not in ('normal', 'daily') or type(value.get('victory')) is not bool:
        return False
    for key in ('elapsed_ms', 'kills', 'level'):
        if type(value.get(key)) is not int or not 0 <= value[key] <= 10000000:
            return False
    for key, names in (('weapons', ('spark', 'blades', 'ring')), ('passives', ('boots', 'heart', 'magnet'))):
        if not isinstance(value.get(key), dict):
            return False
        if any(n not in names or type(v) is not int or not 0 <= v <= 5 for n, v in value[key].items()):
            return False
    return True


class Records:
    def __init__(self, path=None, web=None):
        self.path = Path(path) if path is not None else Path(__file__).parent / '.userdata/records.json'
        self.web = web
        self.persistent = True
        self.entries = {}
        if sys.platform == 'emscripten' and web is None:
            import platform
            try:
                self.web = platform.window.localStorage
            except Exception:
                self.persistent = False
        try:
            if self.web is not None:
                raw = self.web.getItem(STORAGE_KEY)
                raw = str(raw) if raw else ''
            elif sys.platform != 'emscripten':
                raw = self.path.read_text(encoding='utf-8') if self.path.exists() else ''
            else:
                raw = ''
            data = json.loads(raw) if raw and len(raw) <= 200000 else {}
            if isinstance(data, dict) and data.get('schema') == 1 and isinstance(data.get('entries'), dict):
                self.entries = {k: v for k, v in data['entries'].items()
                                if isinstance(k, str) and len(k) <= 160 and valid_result(v)}
        except (ValueError, OSError, TypeError):
            # Corrupt or inaccessible saves must never prevent starting a game.
            self.persistent = False
        except Exception:
            # Browser storage may throw JavaScript security/quota exceptions.
            self.persistent = False

    @staticmethod
    def keys(mode, version, day, preset='normal'):
        if mode == 'normal':
            return [f'normal:{version}']
        return [f'daily:{version}:{day}', f'best:{version}:{preset}']

    def best(self, mode, version, day='', preset='normal', history=False):
        keys = self.keys(mode, version, day, preset)
        return self.entries.get(keys[-1] if history else keys[0])

    def submit(self, result):
        if not valid_result(result):
            return False
        keys = self.keys(result['mode'], result['version'], result['day'], result['preset'])
        improved = False
        for index, key in enumerate(keys):
            old = self.entries.get(key)
            if old is None or rank(result) > rank(old):
                self.entries[key] = json.loads(json.dumps(result))
                if index == 0:
                    improved = True
        # Keep 90 daily results, plus bounded bests for current/previous versions.
        daily = sorted((k for k in self.entries if k.startswith('daily:')),
                       key=lambda k: self.entries[k]['day'], reverse=True)
        other = [k for k in self.entries if not k.startswith('daily:')]
        keep = set(daily[:90] + other[-100:])
        self.entries = {k: v for k, v in self.entries.items() if k in keep}
        self.save()
        return improved

    def save(self):
        raw = json.dumps({'schema': 1, 'entries': self.entries}, ensure_ascii=False)
        try:
            if self.web is not None:
                self.web.setItem(STORAGE_KEY, raw)
            elif sys.platform != 'emscripten':
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix('.tmp')
                temporary.write_text(raw, encoding='utf-8')
                temporary.replace(self.path)
            else:
                self.persistent = False
                return
            self.persistent = True
        except Exception:
            self.persistent = False
