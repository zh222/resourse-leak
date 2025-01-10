import random
import time


class RandomAgent:
    def __init__(self, env):
        self.env = env
        self.table = {}

    def get_action(self, state):
        actions = self.table[state]
        return random.choice(list(actions.keys())) if len(actions) > 0 else 0

    def learn(self, start_time):
        while time.time() - start_time < 3600 * 2:
            state = tuple(self.env.observation['observation'])
            if state not in self.table:
                n = len(self.env.views)
                if n != 0:
                    self.table[state] = {(i / n, 0, 0) : 0 for i in range(n)}
            done = self.env._termination()
            if not done:
                action = self.get_action(state)
                next_state, reward, done, _, _ = self.env.step(action)
                next_state = tuple(next_state['observation'])
                if next_state not in self.table:
                    n = len(self.env.views)
                    self.table[next_state] = {(i / n, 0, 0): 0 for i in range(n)}
            else:
                self.env.reset()

    def save(self, file_name):
        pass


