import copy
import unittest
from rules import Game, Gem, load_config
from challenges import daily_challenge, load_challenges, version_id
from records import Records
from tests.test_challenges import FakeWeb


class CharacterTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()

    def test_knight_starts_with_one_heart_and_full_health(self):
        game = Game(self.config, character='knight')
        level = self.config['characters']['knight']['passives']['heart']
        self.assertEqual(game.passives['heart'], level)
        expected = self.config['hero']['hp'] + level*self.config['passives']['heart_hp']
        self.assertEqual((game.hp, game.max_hp), (expected, expected))
        game.cards = ['heart']
        game.choose_card(0)
        self.assertEqual(game.max_hp, expected+self.config['passives']['heart_hp'])

    def test_mage_damage_bonus_does_not_change_attack_speed_or_level(self):
        game = Game(self.config, character='mage')
        base = self.config['weapons']['spark']
        bonus = self.config['characters']['mage']['spark_damage_levels']*base['damage_per_level']
        self.assertEqual(game.weapons['spark'], 1)
        self.assertEqual(game.weapon_stats('spark')['damage'], base['damage']+bonus)
        self.assertEqual(game.weapon_stats('spark')['interval'], base['interval'])
        preview = game.weapon_stats('spark', 2)
        game.cards = ['spark']
        game.choose_card(0)
        self.assertEqual(game.weapon_stats('spark'), preview)
        self.assertEqual(preview['damage'], base['damage']+base['damage_per_level']+bonus)
        self.assertEqual(game.weapon_stats('blades'), Game(self.config).weapon_stats('blades'))

    def test_ranger_starts_with_boots_and_next_upgrade_stacks(self):
        game = Game(self.config, character='ranger')
        level = self.config['characters']['ranger']['passives']['boots']
        self.assertEqual(game.passives['boots'], level)
        self.assertAlmostEqual(game.speed, self.config['hero']['speed']*(1+level*self.config['passives']['boots_speed_fraction']))
        game.cards = ['boots']
        game.choose_card(0)
        self.assertAlmostEqual(game.speed, self.config['hero']['speed']*(1+(level+1)*self.config['passives']['boots_speed_fraction']))

    def test_role_state_is_fresh_and_never_mutates_configuration(self):
        original = copy.deepcopy(self.config)
        knight = Game(self.config, character='knight')
        knight.hp = 0
        knight.passives['heart'] += 1
        fresh = Game(self.config, character='knight')
        self.assertEqual(fresh.hp, fresh.max_hp)
        self.assertEqual(fresh.passives['heart'], self.config['characters']['knight']['passives']['heart'])
        self.assertEqual(Game(self.config, character='mage').passives['heart'], 0)
        self.assertEqual(self.config, original)

    def test_daily_modifiers_apply_before_starting_bonuses(self):
        cfg = daily_challenge(self.config, load_challenges(), '2026-10-29')['config']
        knight = Game(cfg, character='knight')
        mage = Game(cfg, character='mage')
        ranger = Game(cfg, character='ranger')
        self.assertEqual(knight.hp, cfg['hero']['hp']+cfg['passives']['heart_hp'])
        self.assertEqual(mage.weapon_stats('spark')['damage'], cfg['weapons']['spark']['damage']+cfg['weapons']['spark']['damage_per_level'])
        self.assertAlmostEqual(ranger.speed, cfg['hero']['speed']*(1+cfg['passives']['boots_speed_fraction']))
        self.assertEqual(mage.weapon_stats('spark')['interval'], cfg['weapons']['spark']['interval'])

    def test_new_balance_gets_its_own_record_version(self):
        definitions = load_challenges()
        version = version_id(self.config, definitions)
        self.config['characters']['mage']['spark_damage_levels'] += 1
        self.assertNotEqual(version, version_id(self.config, definitions))

    def test_records_are_separate_per_role(self):
        from challenges import result_for
        records = Records(web=FakeWeb())
        for role in self.config['characters']:
            game = Game(self.config, character=role)
            result = result_for(game, 'normal', 'version:'+role, '2026-10-29')
            records.submit(result)
            self.assertEqual(records.best('normal', 'version:'+role)['character'], role)
        self.assertEqual(len(records.entries), len(self.config['characters']))

    def test_coin_pickups_still_give_enemy_xp(self):
        game = Game(self.config, character='knight')
        amount = self.config['enemies']['slime']['xp']
        game.gems = [Gem(0, 0, amount)]
        game.update()
        self.assertEqual(game.xp, amount)
        self.assertFalse(game.gems)
