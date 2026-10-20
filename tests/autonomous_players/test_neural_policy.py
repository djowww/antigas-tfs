import math
import random
import tempfile
import unittest
from pathlib import Path

from tools.autonomous_players.neural_policy import DeepQPolicy, encode_state


class NeuralPolicyTests(unittest.TestCase):
    def test_shared_replay_learns_when_visible_prey_changes_best_action(self):
        model=DeepQPolicy(seed=7)
        base=dict(floor=7,level=1,health=150,max_health=150,
                  nearby_threats=0,route_confidence=.5,goal='hunt',
                  retreat_available=True)
        for index in range(400):
            prey=bool(index%2)
            state=dict(base,prey_available=prey)
            action='hunt' if (index//2)%2 else 'move'
            reward=2.0 if (action=='hunt')==prey else -2.0
            model.observe(state,action,reward,state,('move','hunt'),terminal=True)
        without_prey=model.q_values(encode_state(dict(base,prey_available=False)))
        with_prey=model.q_values(encode_state(dict(base,prey_available=True)))
        self.assertGreater(without_prey[0],without_prey[1])
        self.assertGreater(with_prey[1],with_prey[0])

    def test_features_are_bounded_and_reject_nonfinite_telemetry(self):
        state=dict(floor=8, level=3, health=95, max_health=150,
                   nearby_threats=2, route_confidence=.7, prey_available=True,
                   food_available=False, retreat_available=True, goal='hunt')
        features=encode_state(state)
        self.assertEqual(len(features),12)
        self.assertTrue(all(-1 <= value <= 1 for value in features))
        with self.assertRaises(ValueError):
            encode_state(dict(state,route_confidence=float('nan')))

    def test_two_hidden_layers_learn_non_linear_xor(self):
        model=DeepQPolicy(seed=7)
        examples=[]
        for a,b in ((0,0),(0,1),(1,0),(1,1)):
            features=(float(a),float(b))+(0.0,)*10
            examples.append((features, 1.0 if a != b else -1.0))
        before=sum((model.q_values(x)[0]-target)**2 for x,target in examples)
        for _ in range(700):
            for features,target in examples:
                model.train_example(features,'move',target)
        after=sum((model.q_values(x)[0]-target)**2 for x,target in examples)
        self.assertLess(after,before*.2)
        self.assertEqual(model.hidden_layers,2)

    def test_action_mask_never_returns_unavailable_action(self):
        model=DeepQPolicy(seed=3)
        state=dict(floor=7,level=1,health=150,max_health=150,
                   nearby_threats=0,route_confidence=.5)
        self.assertEqual(model.choose(state,('move',),random.Random(1)),'move')
        self.assertEqual(model.choose(state,('retreat',),random.Random(1)),'retreat')

    def test_replay_is_bounded_and_checkpoint_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'neural.json'
            model=DeepQPolicy(path,seed=1,max_replay=32)
            state=dict(floor=7,level=1,health=150,max_health=150,
                       nearby_threats=0,route_confidence=.5)
            for _ in range(80):
                model.observe(state,'move',1,state,('move','hunt'),terminal=True)
            self.assertLessEqual(len(model.replay),32)
            model.save()
            restored=DeepQPolicy(path,seed=9,max_replay=32)
            self.assertEqual(restored.updates,model.updates)
            self.assertEqual(restored.q_values(encode_state(state)),model.q_values(encode_state(state)))
            path.write_text('{"broken":true}',encoding='utf-8')
            with self.assertRaises(ValueError):
                DeepQPolicy(path,seed=9)

    def test_nonfinite_training_target_is_rejected_without_weight_change(self):
        model=DeepQPolicy(seed=11)
        state=(0.0,)*12
        before=model.q_values(state)
        with self.assertRaises(ValueError):
            model.train_example(state,'move',math.inf)
        self.assertEqual(model.q_values(state),before)


if __name__=='__main__':
    unittest.main()
