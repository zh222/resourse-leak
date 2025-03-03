import random
import re
import subprocess
import threading
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
from resourse.resourse import (multi_get_resource, multi_init_resource, multi_append_resource, compute_multi_resource_sensitivity,
                               judge_resource, classify_resources)
from apk.apk import component_extract, apktool, install_apks, uninstall_apps
import csv
import os
import subprocess
import time
import json
from threading import Thread
from agent.ResourceQLearning import ResourceQLearning
from agent import global_data


R = [
    "Views",
    "ViewRootImpl",
    "AppContexts",
    "Activities",
    "Assets",
    "AssetManagers",
    "Local Binders",
    "Proxy Binders",
    "Parcel memory",
    "Parcel count",
    "Death Recipients",
    "OpenSSL Sockets",
    "WebViews",
    "java heap",
    "native heap",
    "fd number",
    "db number",
    "wake lock number",
    "socket number",
    "cpu",
    "rss",
]


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_current_activity(device_name):
    command = f"adb -s {device_name} shell dumpsys window | findstr mCurrentFocus"
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    res = memoryInfo.decode().split('/')[-1].split('}')[0]
    if "mCurrentFocus" not in res:
        return memoryInfo.decode().split('/')[-1].split('}')[0]
    return None


def get_device_name():
    command = "adb devices"
    res = []
    result = run_adb_command(command).split('\n')
    for line in result:
        if "List" not in line:
            res.append(line.split()[0])
    return res


def get_android_version():
    # command = "adb shell getprop ro.build.version.release"
    # result = run_adb_command(command)
    return '11'


def jaccard_similarity(state1, state2):
    state1 = np.array(state1)
    state2 = np.array(state2)
    intersection = np.sum(np.logical_and(state1, state2))
    union = np.sum(np.logical_or(state1, state2))
    similarity = intersection / union if union != 0 else 0
    return similarity


class multi_AppEnv(gym.Env):
    def __init__(self, app_package_name, main_activity, version, device_name, port):
        # 基础设置
        self.exe_number = 50  # 中性事件执行次数
        self.OBSERVATION_SPACE = 2000  # 最大组件个数，用于one-hot编码
        self.epi = 0  # 训练的轮次
        self.activities_number = len(activities) + 10
        # Appium 配置
        self.desired_caps = {
            "platformName": "android",
            "platformVersion": version,
            "deviceName": device_name,
            "udid": device_name,
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
        self.device_name = device_name  # 当前模拟器的设备名
        self.port = port  # 当前模拟器的端口号
        self.current_activity = get_current_activity(device_name)  # 顶层activity名
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
        self.resource = multi_get_resource(self.package, self.device_name)  # 当前状态的资源占用，用于设置 reward
        # self.check_activity()

    def reset(self, seed=None, optional=None):
        super().reset(seed=seed)
        self.epi += 1
        self.current_step = 0
        try:
            self._close()
        except:
            pass
        self._start()
        self.current_activity = get_current_activity(self.device_name)
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
            return self.observation, {key: -1000 for key in R}, False, False, {}
        except WebDriverException:
            try:
                self._close()
            except InvalidSessionIdException:
                pass
            self._start()
            self.update_views()
            return self.observation, {key: -1000 for key in R}, True, False, {}
        except Exception as e:
            self._start()
            self.update_views()
            return self.observation, {key: -1000 for key in R}, True, False, {}

    def step2(self, action_name):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())},{self.device_name} step:{self.current_step}")
        action_name = self.normal_action(action_name)
        self.current_step += 1
        current_view = self.views[action_name[0]]
        try:
            self.action(current_view, action_name)
        except Exception as e:
            print("操作失败，pass")
            self.update_views()
            return self.observation, {key: 0 for key in R}, self._termination(), False, {}
        out_side, reward = self.check_activity()
        if len(self.views) == 0:  # 当前页面没有事件则返回上一页
            self.driver.back()
            self.update_views()
            return self.observation, {key: -1000 for key in R}, self._termination(), False, {}
        if out_side:
            try:
                self._close()
            except:
                pass
            self._start()
            self.update_views()
            print(f'{self.device_name}  第{self.epi}轮,第{self.current_step}次训练,跳出app, reward: {reward}')
            return self.observation, reward, self._termination(), False, {}
        print(f'{self.device_name}  第{self.epi}轮, 第{self.current_step}次训练, states:{len(state)}')
        return self.observation, reward, self._termination(), False, {}

    def check_activity(self):
        # 检测是否跳到待测app外，没有则判断是否有资源泄露并计算reward
        if self.package != self.driver.current_package and self.driver.current_package != "com.android.permissioncontroller":
            return True, {key: -1000 for key in R}
        self.update_views()
        self.current_activity = get_current_activity(self.device_name)
        temp_resource = multi_get_resource(self.package, self.device_name)
        reward = {key: -1 for key in R}
        if self.current_activity and (self.current_activity not in list_activities or self.is_doubted_state()):
            list_activities[self.current_activity].append(
                [self.get_tuple_observation(), time.time() - start_time, 0, 0])
            self.Edittext()
            self.scroll_neutral()
            is_bug = self.DOC()
            self.home_return_operation()
            self.notification_operation()
            list_activities[self.current_activity][-1][2] = is_bug
            list_activities[self.current_activity][-1][3] = temp_resource
            self.update_views()
            resource_sensitivity = compute_multi_resource_sensitivity(self.resource, temp_resource, weight)
            if self.get_tuple_observation() not in state:
                multi_append_resource(self.package, data, self.device_name)
                cg, centers = classify_resources(data, global_data.get_previous_centers(), n)
                global_data.set_previous_centers_and_category(cg, centers)
                reward = resource_sensitivity
                state.add(self.get_tuple_observation())
        self.resource = multi_get_resource(self.package, self.device_name)
        return False, reward

    def is_doubted_state(self):
        # 新activity或者与之前相似度差异较大的state视为待测state
        if not list_activities[self.current_activity]:
            return True
        for state, _, _, _ in list_activities[self.current_activity]:
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

    def DOC(self):
        print(f'{self.device_name} 开始执行DOC ' + self.current_activity + str(self.get_tuple_observation()))
        resource = multi_init_resource(self.package, self.device_name)
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
            multi_append_resource(self.package, resource, self.device_name)
        judge_resource(resource)
        if resource['is_bug']:
            bug_report[self.current_activity + '_doc_' + ''.join(list(map(str, self.get_tuple_observation())))]\
                = [resource, time.time() - start_time]
        print(f'{self.device_name} DOC执行结束')
        for bug in resource['is_bug']:
            weight[bug] += 1
        return resource['is_bug']

    def Edittext(self):
        print(f'{self.device_name} 开始执行text ' + self.current_activity + str(self.get_tuple_observation()))
        text_boxes = self.driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.EditText")  # 查找所有文本框
        for text_box in text_boxes:
            resource = multi_init_resource(self.package, self.device_name)
            try:
                for i in range(self.exe_number):
                    text_box.click()  # 选中文本框
                    current_string = ''.join(
                        random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                        for _ in range(random.randint(5, 10)))
                    text_box.send_keys(current_string)
                    text_box.clear()
                    multi_append_resource(self.package, resource, self.device_name)
            except:
                pass
            judge_resource(resource)
            if resource['is_bug']:
                name = self.current_activity + '_text_' + self.return_attribute(text_box)
                if name not in bug_report:
                    bug_report[name] = [resource, time.time() - start_time]
                    for bug in resource['is_bug']:
                        weight[bug] += 1
        print(f'{self.device_name} text 执行完毕')

    def home_return_operation(self):
        print(f'{self.device_name} 开始执行home ' + self.current_activity + str(self.get_tuple_observation()))
        resource = multi_init_resource(self.package, self.device_name)
        for i in range(self.exe_number):
            try:
                self.driver.press_keycode(3)
            except:
                pass
            time.sleep(2)
            try:
                self.driver.activate_app(self.package)
            except:
                pass
            time.sleep(2)
            multi_append_resource(self.package, resource, self.device_name)
        judge_resource(resource)
        if resource['is_bug']:
            bug_report[self.current_activity + '_home_' + ''.join(list(map(str, self.get_tuple_observation())))] \
                = [resource, time.time() - start_time]
        print(f'{self.device_name} home执行结束')
        for bug in resource['is_bug']:
            weight[bug] += 1

    def notification_operation(self):
        print(f'{self.device_name} 开始执行通知栏 ' + self.current_activity + str(self.get_tuple_observation()))
        resource = multi_init_resource(self.package, self.device_name)
        for i in range(self.exe_number):
            try:
                self.driver.open_notifications()
            except:
                pass
            time.sleep(2)
            try:
                self.driver.press_keycode(4)
            except:
                pass
            time.sleep(2)
            multi_append_resource(self.package, resource, self.device_name)
        judge_resource(resource)
        if resource['is_bug']:
            bug_report[self.current_activity + '_notification_' + ''.join(list(map(str, self.get_tuple_observation())))] \
                = [resource, time.time() - start_time]
        print(f'{self.device_name} 通知栏执行结束')
        for bug in resource['is_bug']:
            weight[bug] += 1

    def scroll_neutral(self):
        print(f'{self.device_name} 开始执行滑动操作 ')
        for current_view in self.views.values():
            if current_view['scrollable'] == 'true':
                resource = multi_init_resource(self.package, self.device_name)
                try:
                    bounds = re.findall(r'\d+', current_view['view'].get_attribute('bounds'))
                    bounds = [int(i) for i in bounds]
                    for i in range(self.exe_number):
                        self.scroll_action([0, 0], bounds)
                        time.sleep(2)
                        self.scroll_action([0, 1], bounds)
                        time.sleep(2)
                        multi_append_resource(self.package, resource, self.device_name)
                except:
                    pass
                judge_resource(resource)
                if resource['is_bug']:
                    bug_report[self.current_activity + '_scroll_' + ''.join(
                        list(map(str, self.get_tuple_observation())))] \
                        = [resource, time.time() - start_time]
                for bug in resource['is_bug']:
                    weight[bug] += 1
        print(f'{self.device_name} 滑动操作执行完毕')

    def _termination(self):
        # 一个episode是否结束
        return self.current_step >= self.max_steps

    def one_hot_encoding_activities(self):
        # 获取活动的独热编码
        activity_observation = [0] * self.activities_number
        if self.current_activity in activities:
            index = activities.index(self.current_activity)
            activity_observation[index] = 1
        else:
            index = len(activities)
            activity_observation[index] = 1
            activities.append(self.current_activity)
        return activity_observation

    def one_hot_encoding_widgets(self):
        # 获取小部件的独热编码
        widget_observation = [0] * (self.OBSERVATION_SPACE - self.activities_number)
        for view in self.static_views:
            if view not in widget_list:
                widget_list[view] = len(widget_list)
            index = widget_list[view]
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
                if i >= 5:
                    print('Too Many times tried')
                    try:
                        self._close()
                    except:
                        pass
                    self._start()

    def get_all_views(self):
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
                    self.views.update({i: {'view': e, 'identifier': self.return_attribute(e), 'class_name': tag,
                                           'clickable': clickable, 'scrollable': scrollable,
                                           'long-clickable': long_clickable}})
                self.static_views.append(self.return_attribute(e))
        self.views[i] = {'view': None, 'scrollable': False}
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
        # proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
        #                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        # memoryInfo, errInfo = proc.communicate()
        # app_package_name = memoryInfo.decode().split('/')[0].split(' ')[-1]
        # command = ['adb', 'shell', 'am', 'force-stop', app_package_name]
        # subprocess.run(command, capture_output=True, text=True)
        self.driver.quit()
        pass

    def _start(self):
        i = 0
        while True:
            try:
                self.driver = webdriver.Remote(f'http://127.0.0.1:{self.port}/wd/hub', self.desired_caps)
                time.sleep(5)
                self.current_activity = get_current_activity(self.device_name)
                self.update_views()
                self.observation = self._get_observation()
                break
            except Exception as e:
                print(f"连接失败，尝试重新连接:")
                try:
                    self._close()
                    time.sleep(2)
                except:
                    time.sleep(2)
            i += 1


if __name__ == '__main__':
    apps = global_data.apps
    n = global_data.N  # 把资源分为多少类
    ports = [
        # 端口号，用于与不同的模拟器通信
        '4723',
        '4725',
        '4727',
        '4729'
    ]
    android_version = get_android_version()  # 安卓版本
    devices_name = get_device_name()  # 设备名
    for app, apk_path in apps.items():
        apktool(apk_path)
        package, Main_activity, activities = component_extract(
            f'{apk_path.split(".")[0]}/AndroidManifest.xml')
        install_apks(apk_path, devices_name)
        for j in range(1):
            list_activities = defaultdict(list)  # key为已执行到的活动列表, value为activity中测过的状态
            widget_list = defaultdict(int)  # 元素id列表，id具有唯一性, value记录index
            bug_report = {}  # 发现的老化 bug
            state = set()  # 遍历到的状态
            weight = {key: 1 for key in R}  # 资源的权重
            data = multi_init_resource(package, devices_name[0])
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {n} start")
            start_time = time.time()
            envs = []
            agents = []
            tasks = []
            for i in range(n):
                envs.append(multi_AppEnv(package, Main_activity, android_version, devices_name[i], ports[i]))
                agents.append(ResourceQLearning(envs[i]))
                tasks.append(Thread(target=agents[i].learn, args=(start_time, i + 1)))
                tasks[i].start()
            for i in range(n):
                tasks[i].join()
            with open(f'result/{app}/{j + 1}/multi_{n}_bug_report.json', 'w', encoding='utf-8') as json_file:
                json.dump(bug_report, json_file, ensure_ascii=False, indent=4)
            with open(f'result/{app}/{j + 1}/multi_{n}_activities.csv', 'w', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f)
                for activity in list_activities:
                    csv_writer.writerow([activity])
            with open(f'result/{app}/{j + 1}/multi_{n}_coverage.csv', 'w', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(['bugs', f'activities/{len(activities)}', 'states'])
                csv_writer.writerow([len(bug_report), len(list_activities), len(state)])
            with open(f'result/{app}/{j + 1}/multi_{n}_state_time.csv', 'w', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f)
                csv_writer.writerow(['activity_state', 'time'])
                for activity, value in list_activities.items():
                    if activity:
                        for state in value:
                            csv_writer.writerow([activity + '_' + ''.join(map(str, state[0])), state[1]])
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {n} stop")
        uninstall_apps(package, devices_name)



