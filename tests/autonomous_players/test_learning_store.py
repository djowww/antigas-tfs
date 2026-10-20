import tempfile
import unittest
from pathlib import Path
from tools.autonomous_players.learning_store import LearningStore


class LearningStoreTests(unittest.TestCase):
    def test_agents_have_independent_experiences_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db') as store:
                store.record_transition('A', 'surface', 'stairs', 'cave', {'floor': 8}, 2, 1)
                store.record_transition('B', 'surface', 'wait', 'surface', {'floor': 7}, 0, 1)
                store.checkpoint('A', {'region': 'cave'})
                self.assertEqual(store.summary('A')['transitions'], 1)
                self.assertEqual(store.summary('B')['transitions'], 1)
                self.assertEqual(store.restore_latest('A')['region'], 'cave')

    def test_corrupt_checkpoint_is_quarantined_and_previous_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'learning.db'
            with LearningStore(path) as store:
                store.checkpoint('A', {'version': 1})
                store.checkpoint('A', {'version': 2})
                store.db.execute("UPDATE checkpoints SET payload='broken' WHERE agent='A'")
                store.db.commit()
                with self.assertRaises(ValueError):
                    store.restore_latest('A')
                quarantined = store.quarantine_corrupt('A')
                self.assertTrue(quarantined.exists())

    def test_event_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_events=2) as store:
                for i in range(5):
                    store.record_transition('A', 's', 'wait', 's', {'i': i}, 0, i + 1)
                self.assertLessEqual(store.summary('A')['transitions'], 2)

    def test_extended_observation_state_fits_storage_budget(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db') as store:
                state = '{"' + ('x' * 500) + '"}'
                store.record_transition('A', state, 'move', state, {}, 0, 1)
                store.set_value('A', state, 'move', 1)
                self.assertEqual(store.values('A', state)['move'], 1)

    def test_policy_values_are_persisted_in_learning_store(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db') as store:
                store.set_value('A', 'state', 'hunt', 1.5)
                self.assertEqual(store.values('A', 'state')['hunt'], 1.5)

    def test_agent_budget_counts_agents_with_only_policy_values(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_agents=1) as store:
                store.set_value('A', 'state', 'hunt', 1.5)
                with self.assertRaisesRegex(ValueError,'agent budget exhausted'):
                    store.set_value('B', 'state', 'hunt', 1.5)

    def test_agent_budget_counts_agents_with_only_route_edges(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_agents=1) as store:
                store.route_edge('A', 'surface', 'cave', 428, True, 1)
                with self.assertRaisesRegex(ValueError,'agent budget exhausted'):
                    store.record_transition('B', 'surface', 'hunt', 'cave', {}, 0, 2)

    def test_agent_registry_migrates_existing_learning_rows(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'learning.db'
            with LearningStore(path) as store:
                store.set_value('A','state','hunt',1.5)
                store.db.execute('DROP TABLE agents')
                store.db.commit()
            with LearningStore(path,max_agents=1) as store:
                self.assertEqual(store.db.execute('SELECT agent FROM agents').fetchall(),[('A',)])
                self.assertEqual(store.values('A','state')['hunt'],1.5)
                with self.assertRaisesRegex(ValueError,'agent budget exhausted'):
                    store.set_value('B','state','hunt',1.5)

    def test_agent_budget_lookup_does_not_scan_transition_or_route_history(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d)/'learning.db') as store:
                store.record_transition('A','state','hunt','next',{},0,1)
                statements=[]
                store.db.set_trace_callback(statements.append)
                store._agent('A')
                store.db.set_trace_callback(None)
                self.assertFalse(any('FROM TRANSITIONS' in sql.upper() or 'FROM ROUTE_EDGES' in sql.upper()
                                     for sql in statements))

    def test_history_rotation_uses_agent_scoped_indexes(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d)/'learning.db') as store:
                transition_plan=' '.join(str(row) for row in store.db.execute(
                    'EXPLAIN QUERY PLAN SELECT id FROM transitions WHERE agent=? ORDER BY id DESC LIMIT ?',('A',10)))
                route_plan=' '.join(str(row) for row in store.db.execute(
                    'EXPLAIN QUERY PLAN SELECT rowid FROM route_edges WHERE agent=? ORDER BY at ASC,rowid ASC LIMIT 10',('A',)))
                self.assertIn('idx_learning_transitions_agent_id',transition_plan)
                self.assertIn('idx_learning_route_edges_agent_at',route_plan)

    def test_policy_value_budget_replaces_oldest_value(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_values=1) as store:
                store.set_value('A', 'one', 'hunt', 1)
                store.set_value('A', 'two', 'hunt', 2)
                self.assertEqual(store.values('A', 'one'), {})
                self.assertEqual(store.values('A', 'two')['hunt'], 2)

    def test_checkpoint_generations_are_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_checkpoints=2) as store:
                for version in range(5):
                    store.checkpoint('A', {'version': version})
                self.assertEqual(store.summary('A')['checkpoints'], 2)
                self.assertEqual(store.restore_latest('A')['version'], 4)

    def test_route_edges_rotate_within_budget(self):
        with tempfile.TemporaryDirectory() as d:
            with LearningStore(Path(d) / 'learning.db', max_edges=2) as store:
                for edge in range(4):
                    store.route_edge('A', edge, edge + 1, edge, True, edge)
                self.assertEqual(store.summary('A')['edges'], 2)


if __name__ == '__main__':
    unittest.main()
