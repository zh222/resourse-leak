import random
import time
from agent import global_data
import numpy as np


class ResourceQLearning:
    def __init__(self, env, learning_rate=0.1, discount_factor=0.99, epsilon=0.1):
        self.env = env
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon

    def get_action_resources(self, state, res_type):
        actions = {}
        category = global_data.get_category()
        resources = category[res_type]
        for res in resources:
            global_data.init_q_tables(state, self.env)
            q_tables = global_data.get_q_tables()
            for action in q_tables[res][state].keys():
                if action not in actions:
                    actions[action] = q_tables[res][state][action]
                else:
                    actions[action] += q_tables[res][state][action]
        if np.random.rand() < self.epsilon:
            return random.choice(list(actions.keys()))
        else:
            return max(actions, key=actions.get)

    def get_action(self, state, q_table):
        return max(q_table[state], key=q_table[state].get)

    def update_q_table(self, state, action, reward, next_state):
        q_tables = global_data.get_q_tables()
        for res in q_tables.keys():
            best_next_action = self.get_action(next_state, q_tables[res])
            td_target = reward[res] + self.discount_factor * q_tables[res][next_state][best_next_action]
            td_error = td_target - q_tables[res][state][action]
            global_data.update_q_tables(state, action, res, self.learning_rate, td_error)

    def learn(self, start_time, res_type):
        while time.time() - start_time < 3600 * 2:
            state = tuple(self.env.observation['observation'])
            global_data.init_q_tables(state, self.env)
            done = self.env._termination()
            if not done:
                # 基于所有某一资源类别的 q_table 选择动作
                action = self.get_action_resources(state, res_type)
                next_state, reward, done, _, _ = self.env.step(action)
                next_state = tuple(next_state['observation'])
                global_data.init_q_tables(next_state, self.env)
                self.update_q_table(state, action, reward, next_state)
            else:
                self.env.reset()

