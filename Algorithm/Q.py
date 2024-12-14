import random
import numpy as np


class QLearningAgent:
    def __init__(self, env, learning_rate=0.1, discount_factor=0.99, epsilon=0.1):
        self.env = env
        self.env.reset()
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.q_table = {}

    def get_action(self, state):
        actions = self.q_table[state]
        if np.random.rand() < self.epsilon:
            return random.choice(list(actions.keys()))
        else:
            return max(actions, key=actions.get)

    def update_q_table(self, state, action, reward, next_state):
        best_next_action = self.get_action(next_state)
        td_target = reward + self.discount_factor * self.q_table[next_state][best_next_action]
        td_error = td_target - self.q_table[state][action]
        self.q_table[state][action] += self.learning_rate * td_error

    def learn(self, total_timesteps=2000):
        for _ in range(total_timesteps):
            state = tuple(self.env.observation['observation'])
            if state not in self.q_table:
                n = len(self.env.views)
                if n != 0:
                    self.q_table[state] = {(i / n, 0, 0): 0 for i in range(n)}
            done = self.env._termination()
            if not done:
                action = self.get_action(state)
                next_state, reward, done, _, _ = self.env.step(action)
                next_state = tuple(next_state['observation'])
                if next_state not in self.q_table:
                    n = len(self.env.views)
                    self.q_table[next_state] = {(i / n, 0, 0): 0 for i in range(n)}
                self.update_q_table(state, action, reward, next_state)
            else:
                self.env.reset()

    def predict(self, state, deterministic=True):
        actions = self.get_action(state)
        if deterministic:
            return max(actions, key=actions.get)
        else:
            return random.choice(list(actions.keys()))

    def save(self, path):
        np.save(path, self.q_table)

    def load(self, path):
        self.q_table = np.load(path, allow_pickle=True).item()
