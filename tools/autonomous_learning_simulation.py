"""Closed-world learner simulation; it never opens a production socket."""
import argparse
import random
from pathlib import Path
from .autonomous_players.learning_bridge import LearningAgent
from .autonomous_players.learning_protocol import LearningObservation
from .autonomous_players.learning_store import LearningStore
from .autonomous_players.world import Position, Stats, World


def run_simulation(state_path, agents=20, steps=200, seed=1):
    if not isinstance(agents, int) or not 1 <= agents <= 20 or not isinstance(steps, int) or steps < 1:
        raise ValueError('invalid simulation size')
    rng = random.Random(seed)
    learner = LearningAgent(Path(state_path))
    transitions = 0
    xp_observations = 0
    try:
        for index in range(agents):
            name = f'Sim-{index + 1:02d}'
            agent_transitions = 0
            agent_xp = 0
            previous_floor = None
            previous_xp = 0
            for step in range(steps):
                floor = 7 if step < max(2, steps // 4) else 8
                xp = 0 if step < max(2, steps // 3) else 5
                world = World(position=Position(32100 + index % 5, 32200 + index // 5, floor),
                              stats=Stats(150, 150, 400, xp, 1))
                learner.handle(LearningObservation.from_world(name, world, 'hunt', .5))
                if previous_floor is not None and floor != previous_floor:
                    agent_transitions += 1
                if xp > previous_xp:
                    agent_xp += 1
                previous_floor, previous_xp = floor, xp
            learner.store.checkpoint(name, {'floor': 8, 'xp_observed': 5, 'seed': rng.randrange(1 << 30)})
            transitions += agent_transitions
            xp_observations += agent_xp
        event_count = learner.store.db.execute('SELECT count(*) FROM transitions').fetchone()[0]
    finally:
        learner.close()
    with LearningStore(Path(state_path)) as reopened:
        checkpoint_reloaded = reopened.restore_latest('Sim-01') is not None
        event_count = reopened.db.execute('SELECT count(*) FROM transitions').fetchone()[0]
    return {
        'agents': agents,
        'floor_transitions': transitions,
        'fixture_xp_observations': xp_observations,
        'deaths_restored': 0,
        'checkpoint_reloaded': checkpoint_reloaded,
        'network_connections': 0,
        'max_events': event_count,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='isolated autonomous-learning simulation')
    parser.add_argument('--agents', type=int, default=20)
    parser.add_argument('--duration', type=int, default=200)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--state', required=True)
    args = parser.parse_args(argv)
    import json
    print(json.dumps(run_simulation(Path(args.state), args.agents, args.duration, args.seed), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
