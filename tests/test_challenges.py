import copy
import math
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from challenges import (challenge_day, daily_challenge, draw_modifiers, load_challenges,
                        version_id, result_for)
from records import Records, STORAGE_KEY
from rules import Game, load_config


def forced_definitions(word, kind='curse'):
    """Definitions that force one specific word every single day."""
    pools = {'curse': [], 'boon': [], 'neutral': []}
    pools[kind].append(dict(word))
    return {'combo_types': [{'id': 'solo', kind: 1}], 'modifiers': pools}


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.definitions = load_challenges()

    def test_day_changes_at_beijing_midnight(self):
        self.assertEqual(challenge_day(datetime(2026, 10, 29, 15, 59, tzinfo=timezone.utc)), '2026-10-29')
        self.assertEqual(challenge_day(datetime(2026, 10, 29, 16, 0, tzinfo=timezone.utc)), '2026-10-30')

    def test_repeatable_and_does_not_mutate_base(self):
        original = copy.deepcopy(self.config)
        first = daily_challenge(self.config, self.definitions, '2026-10-29')
        self.assertEqual(first, daily_challenge(self.config, self.definitions, '2026-10-29'))
        self.assertEqual(self.config, original)
        self.assertNotEqual(first['seed'], daily_challenge(self.config, self.definitions, '2026-10-30')['seed'])

    def test_draw_is_deterministic_for_the_same_day(self):
        version = version_id(self.config, self.definitions)
        for day in (f'2026-10-{d}' for d in range(25, 32)):
            combo_a, words_a = draw_modifiers(self.definitions, day, version)
            combo_b, words_b = draw_modifiers(self.definitions, day, version)
            self.assertEqual(combo_a, combo_b, day)
            self.assertEqual([m['id'] for m in words_a], [m['id'] for m in words_b], day)
            self.assertEqual(words_a, words_b, day)

    def test_every_day_draws_three_words_matching_a_combo_type(self):
        for day in (f'2026-11-{d}' for d in range(1, 15)):
            daily = daily_challenge(self.config, self.definitions, day)
            self.assertEqual(len(daily['modifiers']), 3)
            counts = {}
            for mod in daily['modifiers']:
                counts[mod['kind']] = counts.get(mod['kind'], 0) + 1
            combo = next(c for c in self.definitions['combo_types'] if c['id'] == daily['combo'])
            for kind in ('curse', 'boon', 'neutral'):
                self.assertEqual(combo.get(kind, 0), counts.get(kind, 0), day)

    def test_words_never_repeat_within_a_day(self):
        version = version_id(self.config, self.definitions)
        for day in (f'2026-12-{d}' for d in range(1, 8)):
            ids = [m['id'] for m in draw_modifiers(self.definitions, day, version)[1]]
            self.assertEqual(len(ids), len(set(ids)), day)

    def test_modifier_metadata_is_complete(self):
        for kind, pool in self.definitions['modifiers'].items():
            self.assertTrue(pool, kind)
            for mod in pool:
                for key in ('id', 'name', 'short', 'description'):
                    self.assertIn(key, mod, f'{kind}/{mod.get("id")} lacks {key}')
        for combo in self.definitions['combo_types']:
            self.assertEqual(sum(combo.get(k, 0) for k in ('curse', 'boon', 'neutral')), 3)
        daily = daily_challenge(self.config, self.definitions, '2026-10-29')
        self.assertLessEqual(len(daily['preset']['id']), 64)  # records key limit

    def test_numeric_words_apply_described_changes(self):
        base_hp = self.config['hero']['hp']
        expectations = {
            'frenzy': lambda cfg, beh: (cfg['enemies']['bat']['speed'], self.config['enemies']['bat']['speed'] * 1.2),
            'hardened': lambda cfg, beh: (cfg['enemies']['slime']['hp'], 39),
            'frail': lambda cfg, beh: (cfg['hero']['hp'], 70),
            'swarm': lambda cfg, beh: (cfg['waves'][0]['minimum'],
                                        min(self.config['spawn']['cap'], math.ceil(self.config['waves'][0]['minimum'] * 1.25))),
            'swift': lambda cfg, beh: (cfg['hero']['speed'], self.config['hero']['speed'] * 1.2),
            'magnetize': lambda cfg, beh: (cfg['hero']['magnet_radius'], self.config['hero']['magnet_radius'] * 2),
            'elite': lambda cfg, beh: (cfg['weapons']['spark']['damage'], self.config['weapons']['spark']['damage'] * 1.25),
            'slow': lambda cfg, beh: (cfg['enemies']['ghost']['speed'], self.config['enemies']['ghost']['speed'] * 0.9),
        }
        for kind, pool in self.definitions['modifiers'].items():
            for word in pool:
                daily = daily_challenge(self.config, forced_definitions(word, kind), '2026-10-29')
                cfg, beh = daily['config'], daily['config'].get('modifiers', {})
                self.assertEqual(cfg['goal'], self.config['goal'])
                if word['id'] in expectations:
                    self.assertEqual(expectations[word['id']](cfg, beh)[0], expectations[word['id']](cfg, beh)[1])
                if word['id'] == 'basics':
                    self.assertEqual(cfg['hero']['hp'], base_hp * 2)
                    self.assertTrue(beh.get('no_cards'))
                    self.assertEqual(beh.get('basics_damage_scale'), 3)
                    self.assertEqual(beh.get('basics_damage_scale_per_level'), 0.05)
                if word['id'] == 'instakill':
                    self.assertTrue(beh.get('instakill'))
                    self.assertEqual(beh.get('mercy_invincible_seconds'), 1.5)
                if word['id'] == 'feast':
                    self.assertEqual(beh.get('lifesteal'), 0.05)
                if word['id'] == 'haste':
                    self.assertEqual(beh.get('time_scale'), 3)

    def test_conflicting_words_never_cooccur(self):
        definitions = {'combo_types': [{'id': 'pair', 'curse': 2}],
                       'modifiers': {
                           'curse': [{'id': 'a', 'name': 'A', 'short': 'a', 'description': 'a',
                                      'conflicts': ['b'], 'enemy_speed': 1.1},
                                     {'id': 'b', 'name': 'B', 'short': 'b', 'description': 'b',
                                      'enemy_speed': 1.1},
                                     {'id': 'c', 'name': 'C', 'short': 'c', 'description': 'c',
                                      'enemy_speed': 1.1}],
                           'boon': [], 'neutral': []}}
        for day in (f'2027-01-{d}' for d in range(1, 10)):
            _, modifiers = draw_modifiers(definitions, day, 'v-test')
            ids = {m['id'] for m in modifiers}
            self.assertEqual(len(ids), 2, day)
            self.assertFalse({'a', 'b'} <= ids, day)

    def test_gameplay_version_isolates_balance_changes(self):
        version = version_id(self.config, self.definitions)
        self.config['feel']['shake_pixels'] += 1
        self.assertEqual(version, version_id(self.config, self.definitions))
        self.config['skins'] = [{'name': 'cosmetic', 'sprite': 'hero'}]
        self.assertEqual(version, version_id(self.config, self.definitions))
        self.config['hero']['hp'] += 1
        self.assertNotEqual(version, version_id(self.config, self.definitions))

    def test_word_library_change_isolates_records(self):
        version = version_id(self.config, self.definitions)
        changed = copy.deepcopy(self.definitions)
        changed['modifiers']['boon'][0]['lifesteal'] = 0.06
        self.assertNotEqual(version, version_id(self.config, changed))

    def test_daily_upgrade_randomness_independent_of_spawn_rng(self):
        daily = daily_challenge(self.config, self.definitions, '2026-10-29')
        a = Game(daily['config'], seed=daily['seed'], card_seed=daily['card_seed'])
        b = Game(daily['config'], seed=daily['seed'], card_seed=daily['card_seed'])
        for _ in range(100):
            a.circle_position()
        a.gain_xp(a.xp_needed)
        b.gain_xp(b.xp_needed)
        self.assertEqual(a.cards, b.cards)

    def test_same_daily_inputs_produce_same_result(self):
        daily = daily_challenge(self.config, self.definitions, '2026-10-29')
        a = Game(daily['config'], seed=daily['seed'], card_seed=daily['card_seed'])
        b = Game(daily['config'], seed=daily['seed'], card_seed=daily['card_seed'])
        for _ in range(1500):
            for game in (a,b):
                if game.cards:
                    game.choose_card(0)
                game.update((90, 60))
        self.assertEqual((a.elapsed,a.hp,a.kills,a.weapons), (b.elapsed,b.hp,b.kills,b.weapons))
        self.assertEqual([(e.x,e.y,e.hp) for e in a.enemies], [(e.x,e.y,e.hp) for e in b.enemies])

    def test_basics_day_offers_no_cards_but_levels_still_stack(self):
        word = next(m for m in self.definitions['modifiers']['curse'] if m['id'] == 'basics')
        daily = daily_challenge(self.config, forced_definitions(word), '2026-10-29')
        game = Game(daily['config'], seed=daily['seed'], card_seed=daily['card_seed'])
        for expected_level in (2, 3):
            game.gain_xp(game.xp_needed)  # exact level cost, no surplus
            self.assertEqual(game.cards, [])
            self.assertEqual(game.level, expected_level)
            self.assertEqual(game.xp, 0)


class FakeWeb:
    def __init__(self):
        self.raw = None
        self.blocked = False
    def getItem(self, key):
        assert key == STORAGE_KEY
        if self.blocked:
            raise RuntimeError('blocked')
        return self.raw
    def setItem(self, key, raw):
        assert key == STORAGE_KEY
        if self.blocked:
            raise RuntimeError('quota exceeded')
        self.raw = raw


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'records.json'
        self.game = Game()
        self.game.elapsed = 30
        self.result = result_for(self.game, 'normal', 'test-v1', '2026-10-29')

    def test_save_reload_and_equipment_snapshot(self):
        records = Records(path=self.path)
        self.assertTrue(records.submit(self.result))
        self.game.weapons['spark'] = 5
        saved = Records(path=self.path).best('normal','test-v1')
        self.assertEqual(saved, self.result)
        self.assertEqual(saved['weapons']['spark'], 1)

    def test_worse_and_tied_runs_do_not_replace_best(self):
        records = Records(path=self.path)
        records.submit(self.result)
        self.assertFalse(records.submit(self.result))
        worse = dict(self.result, elapsed_ms=29000, kills=999)
        self.assertFalse(records.submit(worse))
        self.assertEqual(records.best('normal','test-v1'), self.result)

    def test_rank_prefers_victory_then_time_kills_level(self):
        records = Records(path=self.path)
        records.submit(self.result)
        for updates in ({'elapsed_ms':31000}, {'elapsed_ms':31000,'kills':3},
                        {'elapsed_ms':31000,'kills':3,'level':2}, {'victory':True,'elapsed_ms':120000}):
            self.assertTrue(records.submit(dict(self.result, **updates)))

    def test_modes_dates_versions_and_same_preset_history_are_separate(self):
        records = Records(path=self.path)
        records.submit(self.result)
        daily = dict(self.result, mode='daily', preset='swift')
        records.submit(daily)
        tomorrow = dict(daily, day='2026-10-30', kills=2)
        records.submit(tomorrow)
        self.assertEqual(records.best('daily','test-v1','2026-10-29','swift'), daily)
        self.assertEqual(records.best('daily','test-v1','2026-10-29','swift',history=True), tomorrow)
        self.assertEqual(records.best('normal','test-v1'), self.result)
        self.assertIsNone(records.best('normal','new-version'))
        self.assertIsNone(records.best('daily','test-v1','2026-10-31','swift'))

    def test_corrupt_and_wrong_shape_saves_do_not_crash(self):
        for raw in ('{', '[]', '{"schema":1,"entries":[]}',
                     '{"schema":1,"entries":{"normal:test-v1":{"victory":true}}}'):
            self.path.write_text(raw)
            self.assertIsNone(Records(path=self.path).best('normal','test-v1'))

    def test_browser_reload_and_storage_failure_preserve_session_best(self):
        web = FakeWeb()
        records = Records(web=web)
        records.submit(self.result)
        self.assertEqual(Records(web=web).best('normal','test-v1'), self.result)
        web.blocked = True
        better = dict(self.result, kills=1)
        records.submit(better)
        self.assertFalse(records.persistent)
        self.assertEqual(records.best('normal','test-v1'), better)
        self.assertFalse(Records(web=web).persistent)

    def test_atomic_file_failure_does_not_destroy_old_save(self):
        records = Records(path=self.path)
        records.submit(self.result)
        records.path.with_suffix('.tmp').mkdir()
        self.assertTrue(records.submit(dict(self.result,kills=1)))
        self.assertFalse(records.persistent)
        self.assertEqual(Records(path=self.path).best('normal','test-v1'), self.result)

    def test_daily_retention_preserves_same_preset_best(self):
        from datetime import date, timedelta
        records = Records(path=self.path)
        for index in range(100):
            day = (date(2026,1,1)+timedelta(days=index)).isoformat()
            records.submit(dict(self.result,mode='daily',preset='swift',day=day,kills=100-index))
        self.assertEqual(sum(k.startswith('daily:') for k in records.entries),90)
        self.assertEqual(records.best('daily','test-v1',preset='swift',history=True)['kills'],100)
