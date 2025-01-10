import random
import re
import subprocess
from collections import defaultdict
import gymnasium as gym
from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.common.touch_action import TouchAction
from gymnasium import spaces
import numpy as np
from appium import webdriver
import time
import xml.etree.ElementTree as ET
from selenium.common import StaleElementReferenceException, WebDriverException, InvalidSessionIdException, \
    InvalidElementStateException
from resourse.resourse import init_resource, append_resource, get_resource, compute_resource_sensitivity, judge_resource


def get_current_activity():
    proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    res = memoryInfo.decode().split('/')[-1].split('}')[0]
    if "mCurrentFocus" not in res:
        return memoryInfo.decode().split('/')[-1].split('}')[0]
    return None


def jaccard_similarity(state1, state2):
    state1 = np.array(state1)
    state2 = np.array(state2)
    intersection = np.sum(np.logical_and(state1, state2))
    union = np.sum(np.logical_or(state1, state2))
    similarity = intersection / union if union != 0 else 0
    return similarity


class AndroidAppEnv(gym.Env):
    def __init__(self, app_package_name, main_activity, al, activities, version, device_name, port, start_time, resource):
        # 基础设置
        self.al = al  # 使用的算法
        self.list_activities = defaultdict(list)  # key为已执行到的活动列表, value为activity中测过的状态
        self.widget_list = defaultdict(int)  # 元素id列表，id具有唯一性, value记录index
        self.exe_number = 50  # 中性事件执行次数
        self.OBSERVATION_SPACE = 2000  # 最大组件个数，用于one-hot编码
        self.epi = 0  # 训练的轮次
        self.bug_report = {}  # 发现的老化缺陷
        self.activities = activities
        self.activities_number = len(self.activities) + 10
        self.start_time = start_time  # 测试起始时间
        self.resource_type = resource  # 用作target的性能指标
        # Appium 配置
        self.desired_caps = {
            "platformName": "android",
            "platformVersion": version,
            "deviceName": device_name,
            "appPackage": app_package_name,
            "appActivity": main_activity,
            "skipDeviceInitialization": True,  # 跳过初始化过程
            "noReset": True,  # 每次启动会话不重置应用状态
            "newCommandTimeout": 6000,  # 与appium服务器的响应时间超过这个值就会出断开连接
            "automationName": "UiAutomator2",
            "sessionOverride": True,  # 覆盖当前会话
            'autoGrantPermissions': True,
        }
        self.driver = webdriver.Remote(f'http://127.0.0.1:{port}/wd/hub', self.desired_caps)
        # 运行时包名与页面元素等信息的存储
        self.package = app_package_name  # 当前app的包名
        self.current_activity = get_current_activity()  # 顶层activity名
        self.static_views = []  # 当前页面所有view的信息
        self.views = {}  # 当前页面的所有event的信息
        self.update_views()  # 更新第一个页面的view
        # 动作空间
        self.action_space = spaces.Box(low=np.array([0, 0]),
                                       high=np.array([0.9999, 0.9999]),
                                       dtype=np.float32)

        # 状态空间
        # self.observation_space = spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_)
        self.observation_space = spaces.Dict(
            {
                "observation": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
                "achieved_goal": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
                "desired_goal": spaces.Box(low=0, high=1, shape=(self.OBSERVATION_SPACE,), dtype=np.bool_),
            }
        )
        # 其他配置
        self.max_steps = 30
        self.current_step = 0
        self.observation = self._get_observation()  # 当前状态-字典类型
        # 已遍历到的状态
        self.state = set()
        self.resource = get_resource(self.package)  # 当前状态的资源占用，用于设置 reward
        self.collect_resource = init_resource(self.package)  # 收集各个状态下的各种资源的大小，用于相关性分析

    def reset(self, seed=None, optional=None):
        super().reset(seed=seed)
        self.epi += 1
        self.current_step = 0
        try:
            self._close()
        except:
            pass
        self._start()
        self.current_activity = get_current_activity()
        self.update_views()

        return self.observation, {}

    def step(self, action_name):
        # 输入为一个动作索引
        # 返回值如下：
        # state：交互后agent的状态。
        # reward：该次交互后得到的奖励。
        # done：类型为bool，True代表该episode已经结束，False则代表没有结束。
        # truncated:
        # info：一个用来debug的字典，可以往里面添加交互过程中的中间变量来debug，如果不需要的话，直接赋为空字典。
        try:
            return self.step2(action_name)
        except StaleElementReferenceException:
            self._start()
            self.check_activity()
            return self.observation, -100.0, False, False, {}
        except WebDriverException:
            try:
                self._close()
            except InvalidSessionIdException:
                pass
            self._start()
            self.update_views()
            return self.observation, -100.0, True, False, {}
        except Exception as e:
            print(e)
            self._start()
            self.update_views()
            return self.observation, -100.0, True, False, {}

    def step2(self, action_name):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}, step:{self.current_step}")
        action_name = self.normal_action(action_name)
        self.current_step += 1
        current_view = self.views[action_name[0]]
        try:
            self.action(current_view, action_name)
        except Exception as e:
            print("操作失败，pass")
            print(e)
            self.update_views()
            return self.observation, 0, self._termination(), False, {}
        out_side, reward = self.check_activity()
        if len(self.views) == 0:  # 当前页面没有事件则返回上一页
            self.driver.back()
            self.update_views()
            return self.observation, -1000, self._termination(), False, {}
        if out_side:
            try:
                self._close()
            except:
                pass
            self._start()
            self.update_views()
            print(f'第{self.epi}轮,第{self.current_step}次训练,跳出app, reward: {reward}')
            return self.observation, reward, self._termination(), False, {}
        print(f'第{self.epi}轮,第{self.current_step}次训练，reward:{reward}, states:{len(self.state)}')
        return self.observation, reward, self._termination(), False, {}

    def check_activity(self):
        # 检测是否跳到待测app外，没有则判断是否有资源泄露并计算reward
        if self.package != self.driver.current_package and self.driver.current_package != "com.android.permissioncontroller":
            return True, -1000
        self.update_views()
        self.current_activity = get_current_activity()
        temp_resource = get_resource(self.package)
        append_resource(self.package, self.collect_resource)
        resource_sensitivity = compute_resource_sensitivity(self.resource, temp_resource, self.resource_type)
        reward = -1
        if self.al == "resources":
            if self.current_activity and (self.current_activity not in self.list_activities or self.is_doubted_state()):
                self.list_activities[self.current_activity].append([self.get_tuple_observation(), time.time() - self.start_time])
                self.DOC()
                self.update_views()
            if self.get_tuple_observation() not in self.state:
                reward = resource_sensitivity
                self.state.add(self.get_tuple_observation())
            self.resource = get_resource(self.package)
            return False, reward
        else:
            if self.current_activity and (self.current_activity not in self.list_activities or self.is_doubted_state()):
                self.list_activities[self.current_activity].append([self.get_tuple_observation(), time.time() - self.start_time])
                self.DOC()
                self.update_views()
                reward = 1000
            else:
                if self.get_tuple_observation() not in self.state:
                    reward = 10
                    self.state.add(self.get_tuple_observation())
            self.resource = get_resource(self.package)
            return False, reward

    def is_doubted_state(self):
        # 新activity或者与之前相似度差异较大的state视为待测state
        if not self.list_activities[self.current_activity]:
            return True
        for state, _ in self.list_activities[self.current_activity]:
            if jaccard_similarity(state, self.get_tuple_observation()) > 0.5:
                return False
        return True

    def normal_action(self, action_name):
        ac = [(action_name[0]) * (len(self.views)), (action_name[1]) * 2]
        ac = list(map(round, ac))
        return ac

    def action(self, current_view, action_number):
        if not current_view['view']:
            self.driver.back()
        elif current_view['class_name'] == 'android.widget.EditText':
            try:
                current_view['view'].clear()
                current_view['view'].click()
                current_string = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                                         for _ in range(random.randint(5, 10)))
                current_view['view'].send_keys(current_string)
            except InvalidElementStateException:
                print('Impossible to insert string')
            except Exception as e:
                print(e)
                pass
        else:
            # 元素可点击
            if current_view['clickable'] == 'true' and current_view['long-clickable'] == 'false':
                current_view['view'].click()

            # 元素既可点击也可长点击
            elif current_view['clickable'] == 'true' and current_view['long-clickable'] == 'true':
                if action_number[1] == 0:
                    current_view['view'].click()
                else:
                    actions = TouchAction(self.driver)
                    actions.long_press(current_view['view']).wait(1000).release().perform()

            # 元素可长点击
            elif current_view['clickable'] == 'false' and current_view['long-clickable'] == 'true':
                actions = TouchAction(self.driver)
                actions.long_press(current_view['view']).wait(1000).release().perform()
            # 元素可滑动
            elif current_view['scrollable'] == 'true':
                bounds = re.findall(r'\d+', current_view['view'].get_attribute('bounds'))
                bounds = [int(i) for i in bounds]
                if (bounds[2] - bounds[0] > 20) and (bounds[3] - bounds[1] > 40):
                    self.scroll_action(action_number, bounds)

    def scroll_action(self, action_number, bounds):
        y = int((bounds[3] - bounds[1]))
        x = int((bounds[2] - bounds[0]) / 2)
        if action_number[1] == 0:
            try:
                self.driver.swipe(x, int(y * 0.3), x, int(y * 0.5), duration=200)
            except InvalidElementStateException:
                print(f'swipe not performed start_position: ({x}, {y}), end_position: ({x}, {y + 20})')
        else:
            try:
                self.driver.swipe(x, int(y * 0.5), x, int(y * 0.3), duration=200)
            except InvalidElementStateException:
                print(f'swipe not performed start_position: ({x}, {y + 20}), end_position: ({x}, {y})')
        time.sleep(1)

    def _termination(self):
        # 一个episode是否结束
        return self.current_step >= self.max_steps

    def one_hot_encoding_activities(self):
        # 获取活动的独热编码
        activity_observation = [0] * self.activities_number
        if self.current_activity in self.activities:
            index = self.activities.index(self.current_activity)
            activity_observation[index] = 1
        else:
            index = len(self.activities)
            activity_observation[index] = 1
            self.activities.append(self.current_activity)
        return activity_observation

    def one_hot_encoding_widgets(self):
        # 获取小部件的独热编码
        widget_observation = [0] * (self.OBSERVATION_SPACE - self.activities_number)
        for view in self.static_views:
            if view not in self.widget_list:
                self.widget_list[view] = len(self.widget_list)
            index = self.widget_list[view]
            widget_observation[index] = 1
        return widget_observation

    def _get_observation(self):
        observation_0 = self.one_hot_encoding_activities()
        observation_1 = self.one_hot_encoding_widgets()
        return {
            'observation': np.array(observation_0 + observation_1),
            'achieved_goal': np.array(observation_0 + observation_1),
            'desired_goal': np.array(observation_0 + observation_1),
            }

    def get_tuple_observation(self):
        return tuple(self.observation['observation'])

    def DOC(self):
        print('开始执行DOC ' + self.current_activity + str(self.get_tuple_observation()))
        resource = init_resource(self.package)
        for i in range(self.exe_number):
            try:
                self.driver.orientation = 'LANDSCAPE' if self.driver.orientation == 'PORTRAIT' else 'PORTRAIT'
            except:
                time.sleep(1)
            time.sleep(3)
            try:
                self.driver.orientation = 'PORTRAIT' if self.driver.orientation == 'LANDSCAPE' else 'LANDSCAPE'
            except:
                time.sleep(1)
            time.sleep(2)
            append_resource(self.package, resource)
        judge_resource(resource)
        if resource['is_bug']:
            self.bug_report[self.current_activity + '_' + ''.join(list(map(str, self.get_tuple_observation())))]\
                = [resource, time.time() - self.start_time]
        print('DOC执行结束')

    def update_views(self):
        # 反复获取当前页面的所有元素信息，防止出现问题
        i = 0
        while i < 15:
            if self.current_activity == 'com.android.launcher3.uioverrides.QuickstepLauncher':
                try:
                    self._close()
                except:
                    pass
                self._start()
            try:
                self.get_all_views()
                break
            except Exception as e:
                i += 1
                print(f"第{i}次获取元素信息失败，重新获取")
                print(e)
                if i >= 5:
                    print('Too Many times tried')
                    try:
                        self._close()
                    except:
                        pass
                    self._start()

    def get_all_views(self):
        # 获取页面内所有可操作的元素
        page = self.driver.page_source
        tree = ET.fromstring(page)
        elements = tree.findall(".//*[@clickable='true']") + tree.findall(".//*[@scrollable='true']") + \
                   tree.findall(".//*[@long-clickable='true']")
        self.static_views = []
        self.views = {}
        tags = set([element.tag for element in elements])
        i = 0
        for tag in tags:
            elements = self.driver.find_elements(AppiumBy.CLASS_NAME, tag)
            for e in elements:
                clickable = e.get_attribute('clickable')
                scrollable = e.get_attribute('scrollable')
                long_clickable = e.get_attribute('long-clickable')
                if (clickable == 'true') or (scrollable == 'true') or (long_clickable == 'true'):
                    identifier = self.return_attribute(e)
                    self.views.update({i: {'view': e, 'identifier': identifier, 'class_name': tag,
                                           'clickable': clickable, 'scrollable': scrollable,
                                           'long-clickable': long_clickable}})
                    i += 1
                if tag == "android.widget.EditText":
                    e.click()
                    current_string = ''.join(
                        random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                        for _ in range(random.randint(5, 10)))
                    e.send_keys(current_string)
                self.static_views.append(self.return_attribute(e))
        self.views[i] = {'view': None}
        self.observation = self._get_observation()

    def return_attribute(self, my_view):
        """
        从给定的视图对象中获取一个唯一的属性值。

        :param my_view: 视图对象
        :return: 唯一的属性值
        """
        # 获取元素id
        attribute_fields = ['resource-id', 'content-desc']
        attribute = None
        for attr in attribute_fields:
            try:
                attribute = my_view.get_attribute(attr)
                if attribute and attribute.strip() != "":
                    break
            except Exception as e:
                pass
        if attribute is None:
            # 构造默认的属性值
            attribute = f"{self.current_activity}.{my_view.get_attribute('class')}."
        return attribute

    def _close(self):
        proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        memoryInfo, errInfo = proc.communicate()
        app_package_name = memoryInfo.decode().split('/')[0].split(' ')[-1]
        command = ['adb', 'shell', 'am', 'force-stop', app_package_name]
        subprocess.run(command, capture_output=True, text=True)
        self.driver.quit()
        pass

    def _start(self):
        i = 0
        while True:
            try:
                self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
                time.sleep(5)
                self.current_activity = get_current_activity()
                self.update_views()
                self.observation = self._get_observation()
                break
            except Exception as e:
                print(f"连接失败，尝试重新连接: {e}")
                try:
                    self._close()
                    time.sleep(2)
                except:
                    time.sleep(2)
            i += 1
            if i % 15 == 0:
                try:
                    subprocess.Popen('adb shell reboot -p',
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
                    time.sleep(30)
                except:
                    pass
                subprocess.Popen('D:\soft\Genymotion\player --vm-name "Google Pixel"',
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
                time.sleep(30)


if __name__ == '__main__':
    pass
    # print(get_activity_lt('com.money.manager.ex.tutorial.TutorialActivity'))