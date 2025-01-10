import random
import time

import numpy as np


class CentralizedQLearning:
    def __init__(self, env, learning_rate=0.1, discount_factor=0.99, epsilon=0.1):
        self.env = env
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon

    def get_action(self, state, q_table):
        actions = q_table[state]
        if np.random.rand() < self.epsilon:
            return random.choice(list(actions.keys()))
        else:
            return max(actions, key=actions.get)

    def update_q_table(self, state, action, reward, next_state, q_table):
        best_next_action = self.get_action(next_state, q_table)
        td_target = reward + self.discount_factor * q_table[next_state][best_next_action]
        td_error = td_target - q_table[state][action]
        q_table[state][action] += self.learning_rate * td_error

    def learn(self, start_time, q_table):
        while time.time() - start_time < 3600 * 2:
            state = tuple(self.env.observation['observation'])
            if state not in q_table:
                n = len(self.env.views)
                if n != 0:
                    q_table[state] = {(i / n, 0, 0): 0 for i in range(n)}
            done = self.env._termination()
            if not done:
                action = self.get_action(state, q_table)
                next_state, reward, done, _, _ = self.env.step(action)
                next_state = tuple(next_state['observation'])
                if next_state not in q_table:
                    n = len(self.env.views)
                    q_table[next_state] = {(i / n, 0, 0): 0 for i in range(n)}
                self.update_q_table(state, action, reward, next_state, q_table)
            else:
                self.env.reset()

