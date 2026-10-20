import unittest

from tools.autonomous_players.world import Creature, Position, Thing, World


class WorldTests(unittest.TestCase):
    def test_prune_keeps_known_creature_metadata_until_server_evicts_it(self):
        position=Position(100,100,7)
        visible_id=0x40000002
        self_id=0x10000001
        known_id=0x40000003
        world=World(self_id=self_id,position=position)
        world.creatures[self_id]=Creature(self_id,'Sim One',position)
        world.creatures[visible_id]=Creature(visible_id,'Rat',position)
        world.creatures[known_id]=Creature(known_id,'Cave Rat',Position(500,500,7))
        world.tiles[position]=[Thing(0,creature_id=self_id),Thing(0,creature_id=visible_id)]

        world.prune()

        self.assertEqual(set(world.creatures),{self_id,visible_id,known_id})
        self.assertEqual(world.creatures[visible_id].position,position)
        self.assertIsNone(world.creatures[known_id].position)


if __name__ == '__main__':
    unittest.main()
