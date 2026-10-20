"""Shared classifications for safe Rook hunting and learning observations."""
from types import MappingProxyType


PASSIVE_CORPSES = MappingProxyType({
    'rabbit': 4173,
    'deer': 4016,
    'chicken': 4330,
    'sheep': 4086,
    'pig': 4116,
})
PASSIVE_CORPSE_NAMES = MappingProxyType({corpse_id: name.title()
                                         for name, corpse_id in PASSIVE_CORPSES.items()})
PASSIVE_FOOD_CREATURES = frozenset(PASSIVE_CORPSES)
HUNTABLE_ROOK_PREY = PASSIVE_FOOD_CREATURES | frozenset({'rat', 'cave rat'})
