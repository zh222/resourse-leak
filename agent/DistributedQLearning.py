import random
import time

import numpy as np


class DistributedQLearning:
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

    def update_q_table(self, state, action, reward, next_state, q_tables, index):
        l = 0
        q_value = 0
        for i in range(len(q_tables)):
            if next_state in q_tables[i]:
                temp_action = self.get_action(state, q_tables[i])
                q_value = q_tables[i][next_state][temp_action]
                l += 1
        td_target = reward + self.discount_factor * q_value / l
        td_error = td_target - q_tables[index][state][action]
        q_tables[index][state][action] += self.learning_rate * td_error

    def learn(self, start_time, q_tables, index):
        while time.time() - start_time < 3600 * 2:
            state = tuple(self.env.observation['observation'])
            if state not in q_tables[index]:
                n = len(self.env.views)
                if n != 0:
                    q_tables[index][state] = {(i / n, 0, 0): 0 for i in range(n)}
            done = self.env._termination()
            if not done:
                # 基于所有 q_table 选择动作
                temp_q_table = {state: {}}
                for i in range(len(q_tables)):
                    if state in q_tables[i]:
                        for k, v in q_tables[i][state].items():
                            if k not in temp_q_table[state]:
                                temp_q_table[state][k] = v
                            else:
                                temp_q_table[state][k] += v
                action = self.get_action(state, temp_q_table)
                next_state, reward, done, _, _ = self.env.step(action)
                next_state = tuple(next_state['observation'])
                if next_state not in q_tables[index]:
                    n = len(self.env.views)
                    q_tables[index][next_state] = {(i / n, 0, 0): 0 for i in range(n)}
                self.update_q_table(state, action, reward, next_state, q_tables, index)
            else:
                self.env.reset()

