"""Tabular Q-learning over safe, explicitly permitted high-level actions."""
import math


class Policy:
    def __init__(self, store, agent, rng, epsilon=0.08, alpha=0.2, gamma=0.9):
        if not all(0 <= v <= 1 for v in (epsilon, alpha, gamma)):
            raise ValueError('invalid learning parameter')
        self.store, self.agent, self.rng = store, agent, rng
        self.epsilon, self.alpha, self.gamma = epsilon, alpha, gamma

    def choose(self, state, allowed_actions):
        actions = sorted(set(allowed_actions))
        if not actions:
            raise ValueError('no safe action')
        if self.rng.random() < self.epsilon:
            return self.rng.choice(actions)
        values = self.store.values(self.agent, state)
        maximum = max(values.get(a, 0) for a in actions)
        return self.rng.choice([a for a in actions if values.get(a, 0) == maximum])

    def update(self, state, action, reward, next_state, allowed_actions, terminal=False):
        if not math.isfinite(reward):
            raise ValueError('nonfinite reward')
        current = self.store.values(self.agent, state).get(action, 0)
        following = self.store.values(self.agent, next_state)
        future = 0 if terminal else max((following.get(a, 0) for a in allowed_actions), default=0)
        value = current + self.alpha * (max(-100, min(100, reward)) + self.gamma * future - current)
        self.store.set_value(self.agent, state, action, value)
        return value
