"""Daily rules and record comparison. Standard library only."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta, date
import hashlib
import json
import math
from pathlib import Path
import random

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


def _pick_without_conflicts(pool, count, taken, rng):
    """Draw up to count distinct words, skipping ids taken or conflicting with them."""
    chosen = []
    while len(chosen) < count:
        available = [mod for mod in pool
                     if mod['id'] not in taken and not (set(mod.get('conflicts', ())) & taken)]
        if not available:
            break
        mod = rng.choice(available)
        chosen.append(dict(mod))
        taken.add(mod['id'])
    return chosen


def draw_modifiers(definitions, day, version):
    """Deterministic daily draw: one combo type, then its modifiers per pool.

    The combo type and the words come from a hash of (version, day), so every
    device faces the same rules on the same day, and the draw changes when the
    word library changes (which also bumps the records version).
    """
    rng = random.Random(f'modifiers:{version}:{day}')
    combo = rng.choice(definitions['combo_types'])
    pools = definitions['modifiers']
    taken = set()
    modifiers = []
    for kind in ('curse', 'boon', 'neutral'):
        for mod in _pick_without_conflicts(pools.get(kind, []), combo.get(kind, 0), taken, rng):
            modifiers.append({**mod, 'kind': kind})
    return combo, modifiers


def _apply_modifier_fields(config, modifiers):
    """Apply numeric fields: absolute overrides first, then order-free multipliers.

    Order independence matters: several speed/HP words can coexist on one day,
    and their product must not depend on the draw order.
    """
    for mod in modifiers:
        if 'hero_hp' in mod:
            config['hero']['hp'] = mod['hero_hp']
    hero_speed = magnet = enemy_speed = enemy_hp = weapon_damage = wave_size = 1.0
    enemy_xp = damage_taken = 1.0
    for mod in modifiers:
        hero_speed *= mod.get('hero_speed', 1)
        magnet *= mod.get('magnet', 1)
        enemy_speed *= mod.get('enemy_speed', 1)
        enemy_hp *= mod.get('enemy_hp', 1)
        enemy_xp *= mod.get('enemy_xp', 1)
        damage_taken *= mod.get('damage_taken', 1)
        weapon_damage *= mod.get('weapon_damage', 1)
        wave_size *= mod.get('wave_size', 1)
        if mod.get('hero_hp_scale'):
            config['hero']['hp'] = round(config['hero']['hp'] * mod['hero_hp_scale'])
        if 'cards' in mod:
            # Offering size is an override, not a multiplier; the windfall and
            # single_choice words are marked conflicting, so they never co-occur.
            config['growth']['cards'] = int(mod['cards'])
    config['hero']['speed'] *= hero_speed
    config['hero']['magnet_radius'] *= magnet
    for enemy in config['enemies'].values():
        enemy['speed'] *= enemy_speed
        enemy['hp'] = math.ceil(enemy['hp'] * enemy_hp)
        enemy['xp'] = round(enemy['xp'] * enemy_xp)
        enemy['damage'] *= damage_taken
    for name in ('spark', 'blades', 'ring'):
        for stat in ('damage', 'damage_per_level'):
            config['weapons'][name][stat] *= weapon_damage
    for wave in config['waves']:
        wave['minimum'] = min(config['spawn']['cap'], math.ceil(wave['minimum'] * wave_size))


def _apply_modifier_behaviour(config, modifiers):
    """Collect behaviour flags into config['modifiers'] for the rules layer.

    Normal runs carry no 'modifiers' section at all, so every flag defaults to
    off and the classic rules stay untouched.
    """
    behaviour = {}
    for mod in modifiers:
        if mod.get('no_cards'):
            behaviour['no_cards'] = True
            behaviour['basics_damage_scale'] = mod.get('weapon_damage_scale', 1)
            behaviour['basics_damage_scale_per_level'] = mod.get('weapon_damage_scale_per_level', 0)
        if mod.get('instakill'):
            behaviour['instakill'] = True
            behaviour['mercy_invincible_seconds'] = mod.get('mercy_invincible_seconds', 0)
        if 'lifesteal' in mod:
            behaviour['lifesteal'] = mod['lifesteal']
        if 'time_scale' in mod:
            behaviour['time_scale'] = int(mod['time_scale'])
        if mod.get('fog'):
            behaviour['fog'] = True
        if 'boss_at' in mod:
            behaviour['boss_at'] = mod['boss_at']
        if 'boss_schedule' in mod:
            behaviour['boss_schedule'] = mod['boss_schedule']
    if behaviour:
        config['modifiers'] = behaviour
    return behaviour


def daily_challenge(base, definitions, day=None):
    day = day or challenge_day()
    version = version_id(base, definitions)
    combo, modifiers = draw_modifiers(definitions, day, version)
    config = deepcopy(base)
    _apply_modifier_fields(config, modifiers)
    _apply_modifier_behaviour(config, modifiers)
    digest = hashlib.sha256(f'{version}:{day}'.encode()).digest()
    return {'day': day, 'version': version, 'combo': combo['id'],
            'modifiers': [{'id': mod['id'], 'name': mod['name'],
                           'short': mod.get('short', ''), 'description': mod['description'],
                           'kind': mod['kind']} for mod in modifiers],
            'preset': {'id': '+'.join(mod['id'] for mod in modifiers),
                       'name': ' · '.join(mod['name'] for mod in modifiers)},
            'config': config,
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
