"""Daily rules and record comparison. Standard library only."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta, date
import hashlib
import json
import math
from pathlib import Path

CHALLENGE_ZONE = timezone(timedelta(hours=8))


def challenge_day(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(CHALLENGE_ZONE).date().isoformat()


def load_challenges():
    return json.loads((Path(__file__).parent / 'data/challenges.json').read_text(encoding='utf-8'))


def version_id(config, definitions):
    # Ignore presentation changes; isolate records when gameplay or daily rules change.
    rules = {k: v for k, v in config.items() if k not in ('art', 'audio', 'feel', 'screen', 'skins')}
    payload = json.dumps([rules, definitions], sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def daily_challenge(base, definitions, day=None):
    day = day or challenge_day()
    ordinal = date.fromisoformat(day).toordinal()
    preset = definitions['presets'][ordinal % len(definitions['presets'])]
    config = deepcopy(base)
    config['hero']['speed'] *= preset.get('hero_speed', 1)
    config['hero']['hp'] = preset.get('hero_hp', config['hero']['hp'])
    config['hero']['magnet_radius'] *= preset.get('magnet', 1)
    for enemy in config['enemies'].values():
        enemy['speed'] *= preset.get('enemy_speed', 1)
        enemy['hp'] = math.ceil(enemy['hp'] * preset.get('enemy_hp', 1))
    for name in ('spark', 'blades', 'ring'):
        for stat in ('damage', 'damage_per_level'):
            config['weapons'][name][stat] *= preset.get('weapon_damage', 1)
    for wave in config['waves']:
        wave['minimum'] = min(config['spawn']['cap'], math.ceil(wave['minimum'] * preset.get('wave_size', 1)))
    version = version_id(base, definitions)
    digest = hashlib.sha256(f'{version}:{day}'.encode()).digest()
    return {'day': day, 'version': version, 'preset': preset, 'config': config,
            'seed': int.from_bytes(digest[:8], 'big'),
            'card_seed': int.from_bytes(digest[8:16], 'big')}


def result_for(game, mode, version, day, preset='normal'):
    return {'mode': mode, 'version': version, 'day': day, 'preset': preset,
            'character': game.character,
            'victory': bool(game.victory), 'elapsed_ms': round(game.elapsed * 1000),
            'kills': game.kills, 'level': game.level,
            'weapons': dict(game.weapons), 'passives': dict(game.passives)}


def rank(result):
    return (result['victory'], result['elapsed_ms'], result['kills'], result['level'])


def summary(result):
    if not result:
        return '暂无纪录'
    seconds = result['elapsed_ms'] // 1000
    return f"{'通关' if result['victory'] else '生存'} {seconds//60}:{seconds%60:02d} · 击败 {result['kills']} · {result['level']}级"
