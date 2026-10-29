import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from challenges import challenge_day, daily_challenge, load_challenges, version_id, result_for
from records import Records, STORAGE_KEY
from rules import Game, load_config


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

    def test_all_presets_match_described_modifiers(self):
        days = [daily_challenge(self.config, self.definitions, f'2026-10-{d}') for d in range(25,29)]
        self.assertEqual(len({d['preset']['id'] for d in days}), 4)
        for daily in days:
            cfg, name = daily['config'], daily['preset']['id']
            self.assertEqual(cfg['goal'], self.config['goal'])
            if name == 'swift':
                self.assertEqual(cfg['hero']['speed'], self.config['hero']['speed']*1.2)
                self.assertEqual(cfg['enemies']['demon']['speed'], self.config['enemies']['demon']['speed']*1.2)
            elif name == 'gems':
                self.assertEqual(cfg['hero']['magnet_radius'], self.config['hero']['magnet_radius']*2)
                self.assertEqual(cfg['enemies']['slime']['hp'], 39)
            elif name == 'tough':
                self.assertEqual(cfg['hero']['hp'], 70)
                self.assertEqual(cfg['weapons']['spark']['damage'], 25)
            else:
                self.assertEqual(cfg['waves'][0]['minimum'], 15)
                self.assertEqual(cfg['enemies']['bat']['speed'], 90)

    def test_gameplay_version_isolates_balance_changes(self):
        version = version_id(self.config, self.definitions)
        self.config['feel']['shake_pixels'] += 1
        self.assertEqual(version, version_id(self.config, self.definitions))
        self.config['hero']['hp'] += 1
        self.assertNotEqual(version, version_id(self.config, self.definitions))

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
