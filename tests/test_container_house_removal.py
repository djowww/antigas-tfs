from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerHouseRemovalTests(unittest.TestCase):
    def test_container_uses_house_tile_of_its_actual_location(self):
        container = (ROOT / "src" / "container.cpp").read_text(encoding="utf-8")
        start = container.index("ReturnValue Container::queryRemove(")
        end = container.index("Cylinder* Container::queryDestination(", start)
        function = container[start:end]
        self.assertIn("if (!getHoldingPlayer())", function)
        self.assertIn("dynamic_cast<const HouseTile*>(getTile())", function)
        self.assertIn("houseTile->queryRemoveFromContainer(actor)", function)

    def test_nested_container_policy_does_not_use_tile_membership_check(self):
        source = (ROOT / "src" / "housetile.cpp").read_text(encoding="utf-8")
        start = source.index("ReturnValue HouseTile::queryRemoveFromContainer(")
        end = source.index("\n}", start)
        policy = source[start:end]
        self.assertIn("ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS", policy)
        self.assertIn("house->isInvited(actorPlayer)", policy)
        self.assertNotIn("return Tile::queryRemove(", policy)


if __name__ == "__main__":
    unittest.main()
