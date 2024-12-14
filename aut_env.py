import random
import re
import subprocess
from collections import defaultdict
from scipy.stats import linregress
import gymnasium as gym
from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.common.touch_action import TouchAction
from gymnasium import spaces
import numpy as np
from loguru import logger
from multiprocessing import Process
from appium import webdriver
import time
import xml.etree.ElementTree as ET
from hashlib import md5
from selenium.common import StaleElementReferenceException, WebDriverException, InvalidSessionIdException, \
    InvalidElementStateException
from util.memory import get_memory, init_resource, append_resource, gc
from util.component import get_activity_stack, get_services, run_adb_command
from util.neutral_event import open_service, close_service, open_receiver



def get_current_activity():
    proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    res = memoryInfo.decode().split('/')[-1].split('}')[0]
    if "mCurrentFocus" not in res:
        return memoryInfo.decode().split('/')[-1].split('}')[0]
    return None


def get_device_name():
    command = "adb devices"
    result = run_adb_command(command).split('\n')[1]
    return result.split()[0]


def get_android_version():
    command = "adb shell getprop ro.build.version.release"
    result = run_adb_command(command)
    return result


def bug_handler(bug_queue, epi):
    subprocess.Popen('adb logcat -c', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, encoding='gbk')
    proc = subprocess.Popen(['adb', 'logcat'], stdout=subprocess.PIPE)
    while True:
        dump_bug = ''
        try:
            temp = proc.stdout.readline().decode('utf-8')
        except UnicodeDecodeError:
            temp = ''
        if temp.find('FATAL EXCEPTION') > 0:
            dump_bug += temp[temp.find('FATAL EXCEPTION'):]
            try:
                temp = proc.stdout.readline().decode('utf-8')
            except UnicodeDecodeError:
                temp = ''
            while temp.find('E AndroidRuntime:') > 0:
                dump_bug += temp[temp.find('E AndroidRuntime:'):]
                temp = proc.stdout.readline().decode('utf-8')
            bug_queue[epi] = dump_bug
            logger.error('A bug occurred, relaunching application')


class AndroidAppEnv(gym.Env):
    def __init__(self, app_package_name, activity_name, al, activities, services, receivers, providers):
        # 基础设置
        self.al = al  # 使用的算法
        self.list_activities = defaultdict(int)  # 已执行到的活动列表, value存储活动的index
        self.list_services = []  # 已执行到的服务列表
        self.list_receivers = []  # 执行到的广播接收器
        self.list_providers = []  # 执行到的内容分析器
        self.widget_list = []  # 元素id列表，id具有唯一性
        self.strings = ["546197961", "123456789"]  # 元素为文本框时选择输入的文本信息
        self.exe_number = 100  # 中性事件执行次数
        self.state_number = 5  # 状态到达state_number次之后才会判断斜率
        self.OBSERVATION_SPACE = 2000  # 最大组件个数，用于one-hot编码
        self.outside = False  # 是否跳出了待测app
        self.epi = -1  # 训练的轮次
        self.bug_report = {}  # 发现的内存泄漏bug
        self.bug = False  # 是否发现了内存泄漏
        self.done_test = set()  # 已测过的中性事件
        self.new_activity = False  # 是否发现了新activity
        self.md5 = ""  # 当前状态的md5值

        # 四大组件列表
        self.activities = activities
        self.services = services
        self.receivers = receivers
        self.providers = providers

        # Appium 配置
        self.desired_caps = {
            "platformName": "android",
            "platformVersion": get_android_version(),
            "deviceName": get_device_name(),
            "appPackage": app_package_name,
            "appActivity": activity_name,
            "skipDeviceInitialization": True,
            "noReset": True,
            "newCommandTimeout": 6000,
            "automationName": "UiAutomator2",
            "dontStopAppOnReset": True,
            "sessionOverride": True,
            "fullReset": False,
        }
        self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
        # 运行时包名与页面元素等信息的存储
        self.package = app_package_name  # 当前app的包名
        self.activity = activity_name
        self.current_activity = get_current_activity()  # 当前活动的包名
        self.views = {}  # 当前页面的所有元素信息
        self.update_views()  # 更新第一个页面的view
        self.bug_queue = {}  # app出现的崩溃bug
        self.bug_proc_pid = self.start_bug_handler()  # 开启bug检测
        # 动作空间
        self.action_space = spaces.Box(low=np.array([0, 0, 0]),
                                       high=np.array([0.9999, 0.9999, 0.9999]),
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
        self.max_steps = 50
        self.current_step = 0
        self.observation = self._get_observation()  # 当前状态
        # 已遍历到的状态以及之前遍历到的内存值, 三元组为[上次遍历到时的内存大小，内存上升次数，遍历到的总次数]
        self.state = {tuple(self.observation['observation']): [get_memory(self.package), 0,
                                                               0]}
        self.aging_metric = []  # 每一轮训练开始收集老化指标
        self.memory = []  # 每一轮训练开始收集内存指标
        if self.al == 'cov':
            self.DOC()
            self.run_menu_bars()
            self.run_text_boxes()
        self.run_receiver()

    def reset(self, seed=None, optional=None):
        super().reset(seed=seed)
        self.md5 = ""
        self.epi += 1
        self.current_step = 0
        try:
            self._close()
        except:
            pass
        self._start()
        self.current_activity = get_current_activity()
        self.update_views()
        gc(self.package)
        self.aging_metric.append(self.get_aging_metric('de.taz.app.android.ui.search.SearchActivity'))
        self.memory.append(get_memory(self.package))
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
        except:
            self._start()
            self.update_views()
            return self.observation, -100.0, True, False, {}

    def step2(self, action_name):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}, step:{self.current_step}")
        action_name = self.normal_action(action_name)
        self.current_step += 1
        if action_name[0] >= len(self.views):
            self.system_action(action_name[0] - len(self.views))
        else:
            current_view = self.views[action_name[0]]
            try:
                self.action(current_view, action_name)
            except:
                print("操作失败，pass")
                self.driver.back()
                self.update_views()
                return self.observation, 0, self._termination(), False, {}
        out_side = self.check_activity()
        if out_side:
            try:
                self._close()
            except:
                pass
            self._start()
            self.update_views()
            print(f'第{self.epi}轮,第{self.current_step}次训练,跳出app')
            return self.observation, -100, self._termination(), False, {}
        if len(self.views) == 0:  # 当前页面没有事件则返回上一页
            self.system_action(1)
            self.update_views()
            return self.observation, -100, self._termination(), False, {}
        if self.al == 'mem':
            reward = self._reward_memory()
        elif self.al == 'cov':
            reward = self._reward_cov()
        else:
            reward = 0
        print(f'第{self.epi}轮,第{self.current_step}次训练，reward:{reward}, states:{len(self.state)}')
        return self.observation, reward, self._termination(), False, {}

    def check_activity(self):
        self.update_views()
        temp_activity = get_current_activity()
        # 检测是否跳到待测app外
        if (self.package != self.driver.current_package) or (temp_activity is None) or \
                (temp_activity.find('com.facebook.FacebookActivity') >= 0):
            return True
        return False

    def normal_action(self, action_name):
        ac = [(action_name[0]) * (len(self.views)), (action_name[1]) * len(self.strings), (action_name[2]) * 2]
        ac = list(map(round, ac))
        return ac

    def system_action(self, number):
        if number == 1:  # 返回键
            self.driver.press_keycode(4)

    def action(self, current_view, action_number):
        if current_view['class_name'] == 'android.widget.EditText':
            try:
                current_view['view'].clear()
                current_view['view'].click()
                # current_string = self.strings[action_number[1]]
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
                if action_number[2] == 0:
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
        if action_number[2] == 0:
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
        activity_observation = [0] * (len(self.activities) + 10)
        temp = [self.current_activity] if self.al == 'cov' else get_activity_stack(self.package)
        for activity in temp:
            if activity in self.list_activities:
                activity_observation[self.list_activities[activity]] = 1
            else:
                self.new_activity = True
                activity_observation[len(self.list_activities)] = 1
                self.list_activities[activity] = len(self.list_activities)
        return activity_observation

    def one_hot_encoding_services(self):
        # 获取服务的独热编码
        service_observation = [0] * (len(self.services) + 10)
        temp = get_services(self.package)
        for service in temp:
            if service in self.list_services:
                index = self.list_services.index(service)
                service_observation[index] = 1
            else:
                service_observation[len(self.list_services)] = 1
                self.list_services.append(service)
        return service_observation

    def one_hot_encoding_widgets(self):
        # 获取小部件的独热编码
        widget_observation = [0] * (self.OBSERVATION_SPACE - len(self.activities) - len(self.services) - 20)
        for _, item in self.views.items():
            identifier = item['identifier']
            if identifier in self.widget_list:
                index = self.widget_list.index(identifier)
                widget_observation[index] = 1
            else:
                self.widget_list.append(identifier)
                widget_observation[len(self.widget_list) - 1] = 1
        return widget_observation

    def _get_observation(self):
        observation_0 = self.one_hot_encoding_activities()
        observation_1 = self.one_hot_encoding_services()
        observation_2 = self.one_hot_encoding_widgets()
        return {
            'observation': np.array(observation_0 + observation_1 + observation_2),
            'achieved_goal': np.array(observation_0 + observation_1 + observation_2),
            'desired_goal': np.array(observation_0 + observation_1 + observation_2),
            }

    def _reward_cov(self):
        state = tuple(self.observation['observation'])
        if state not in self.state:
            temp_memory = get_memory(self.package)
            up_number = self.state[state][2] if temp_memory - self.state[state][0] <= 0 else self.state[state][2] + 1
            self.state[state] = [temp_memory, self.state[state][1] + 1, up_number]
        if self.new_activity:  # 新 activity 给很大奖励,且执行DOC
            reward = 50

            self.DOC()
            self.run_service()
            self.run_menu_bars()
            self.run_text_boxes()
            self.new_activity = False
        elif state not in self.state:  # 没遇到过此状态给小奖励，且收集中性事件并执行
            reward = 10
            self.run_menu_bars()
            self.run_text_boxes()
            self.state[tuple(self.observation['observation'])] = [0, 0, 0]
        else:  # 否则不给奖励
            reward = -1
        return reward

    def _reward_memory(self):
        state = tuple(self.observation['observation'])
        if self.new_activity:  # 新 activity 给很大奖励
            reward = 10
            self.new_activity = False
            self.state[state] = [get_memory(self.package), 1, 0]
        else:
            if state not in self.state:  # 没遇到过此状态给小奖励
                reward = 5
                self.state[state] = [get_memory(self.package), 1, 0]
            else:
                temp_memory = get_memory(self.package)
                reward = temp_memory - self.state[state][0]
                up_number = self.state[state][2] if reward <= 0 else self.state[state][2] + 1
                self.state[state] = [temp_memory, self.state[state][1] + 1, up_number]
                if self.state[state][2] / self.state[state][1] > 0.5 and self.state[state][1] >= 5:
                    try:
                        self.DOC()
                        self.run_service()
                        self.run_menu_bars()
                        self.run_text_boxes()
                    except Exception as e:
                        print("中性事件执行错误")
                        print(e)
                    if self.bug:
                        reward = -50
                        self.bug = False
        return reward

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
            except:
                i += 1
                print(f"第{i}次获取元素信息失败，重新获取")
                if i >= 15:
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
        page = page.replace('enabled="true"', '').replace('enabled="false"', '').replace('checked="false"', '') \
            .replace('checked="true"', '')
        temp_md5 = md5(page.encode()).hexdigest()
        if temp_md5 != self.md5:
            self.md5 = temp_md5
            elements = tree.findall(".//*[@clickable='true']") + tree.findall(".//*[@scrollable='true']") + \
                       tree.findall(".//*[@long-clickable='true']")
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
            self.views.update({i: {'view': 'back', 'identifier': 'back', 'class_name': 'class_name', 'clickable': False,
                                   'scrollable': False, 'long-clickable': False}})
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
        bounds = my_view.get_attribute('bounds')  # 加上坐标信息来唯一确定一个元素

        return attribute + bounds

    def _close(self):
        # proc = subprocess.Popen("adb shell dumpsys window | findstr mCurrentFocus",
        #                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        # memoryInfo, errInfo = proc.communicate()
        # app_package_name = memoryInfo.decode().split('/')[0].split(' ')[-1]
        # command = ['adb', 'shell', 'am', 'force-stop', app_package_name]
        # subprocess.run(command, capture_output=True, text=True)
        # self.driver.quit()
        pass

    def _start(self):
        i = 0
        while True:
            try:
                self.driver.execute_script('mobile: shell', {
                    'command': 'am start -n de.taz.android.app.free/de.taz.app.android.ui.splash.SplashActivity -f 0x10008000'
                })
                # if not self.driver or not self.driver.session_id:
                # self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
                # else:
                #     self.driver.execute_script('mobile: startActivity', {
                #         'appPackage': self.package,  # 应用包名
                #         'appActivity': self.activity,  # 主 Activity 的类名
                #         'flags': ['FLAG_ACTIVITY_NEW_TASK', 'FLAG_ACTIVITY_CLEAR_TOP']  # 清空任务栈
                #     })
                break
            except Exception as e:
                print(f"连接失败，尝试重新连接: {e}")
                try:
                    # self._close()
                    self.driver.quit()
                    self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
                    time.sleep(2)

                except:
                    self.driver = webdriver.Remote('http://127.0.0.1:4723/wd/hub', self.desired_caps)
                    time.sleep(2)
            i += 1
            # if i % 5 == 0:
            #     try:
            #         subprocess.Popen('adb shell reboot -p',
            #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
            #         time.sleep(30)
            #     except:
            #         pass
            #     subprocess.Popen('D:\soft\Genymotion\player --vm-name "Google Pixel"',
            #                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
            #     time.sleep(30)

    def DOC(self):
        print('开始执行DOC')
        if self.current_activity not in self.done_test:
            resource = init_resource(self.package)
            for _ in range(self.exe_number):
                try:
                    self.driver.orientation = 'LANDSCAPE' if self.driver.orientation == 'PORTRAIT' else 'PORTRAIT'
                except:
                    time.sleep(1)
                self.driver.implicitly_wait(6)
                try:
                    self.driver.orientation = 'PORTRAIT' if self.driver.orientation == 'LANDSCAPE' else 'LANDSCAPE'
                except:
                    time.sleep(1)
                self.driver.implicitly_wait(6)
                append_resource(self.package, resource)
            self.compute(resource, "activity", self.current_activity)
            self.done_test.add(self.current_activity)
        print('DOC执行结束')

    def run_service(self):
        print("开始执行services")
        services = get_services(self.package)
        for service in services:
            if service not in self.done_test:
                resource = init_resource(self.package)
                for _ in range(self.exe_number):
                    open_service(self.package, service)
                    time.sleep(3)
                    close_service(self.package, service)
                    append_resource(self.package, resource)
                self.compute(resource, "service", service)
                self.done_test.add(service)
        print("services执行结束")

    def run_receiver(self):
        print("开始执行receiver")
        for receiver, actions in self.receivers.items():
            for action in actions:
                resource = init_resource(self.package)
                for _ in range(self.exe_number):
                    open_receiver(self.package, receiver, action)
                    time.sleep(5)
                    append_resource(self.package, resource)
                self.compute(resource, "receiver", receiver + action)
                self.done_test.add(receiver + action)
        print("receiver执行结束")

    def run_menu_bars(self):
        print('开始搜索并执行菜单栏')
        menu_bars = self.driver.find_elements(by='class name', value='android.widget.Toolbar')
        for menu_bar in menu_bars:
            name = self.return_attribute(menu_bar)
            if f"{self.current_activity}_{name}" not in self.done_test:
                resource = init_resource(self.package)
                for _ in range(self.exe_number):
                    menu_bar.click()
                    time.sleep(1)  # 等待一段时间以便观察状态变化
                    self.driver.back()  # 返回上一级
                    append_resource(self.package, resource)
                self.compute(resource, "menu", f"{self.current_activity}_{name}")
                self.done_test.add(f"{self.current_activity}_{name}")
        print("菜单栏执行结束")

    def run_text_boxes(self):
        print('开始搜索并执行文本框')
        text_boxes = self.driver.find_elements(by='class name', value='android.widget.EditText')
        for text_box in text_boxes:
            name = self.return_attribute(text_box)
            if f"{self.current_activity}_{name}" not in self.done_test:
                resource = init_resource(self.package)
                for _ in range(self.exe_number):
                    text_box.click()
                    current_string = ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
                                             for _ in range(random.randint(5, 10)))
                    text_box.send_keys(current_string)
                    text_box.clear()
                    try:
                        self.driver.hide_keyboard()
                    except:
                        pass
                    append_resource(self.package, resource)
                self.compute(resource, "text", f"{self.current_activity}_{name}")
                self.done_test.add(f"{self.current_activity}_{name}")
        print('文本框执行结束')

    def compute(self, resource, c, name):
        y = np.array(resource['memory'])
        x = np.array([i + 1 for i in range(len(y))])
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        if slope > 0.1 and p_value < 0.01:
            print(f"发现{c}类bug")
            self.bug = True
            resource['classify'] = c
            resource['memory_slope'] = slope
            resource['memory_p_value'] = p_value
            self.bug_report[name] = resource
        else:
            print('未发现bug')

    def get_activity_lt(self, activity_name):
        command = f'adb shell am start -W -n {self.package}/{activity_name}'
        res = run_adb_command(command).split('\n')
        for r in res:
            if 'TotalTime' in r:
                return float(r.split(' ')[-1])
        return 0

    def get_aging_metric(self, activity_name):
        lt = []
        for i in range(self.exe_number):
            lt.append(self.get_activity_lt(activity_name))
            time.sleep(2)
            self.driver.press_keycode(4)  # 返回上一activity
            time.sleep(2)
        return sum(lt) / self.exe_number

    def start_bug_handler(self):
        bug_proc = Process(name='bug_handler', target=bug_handler, args=(self.bug_queue, self.epi))
        bug_proc.daemon = True
        bug_proc.start()
        return bug_proc.pid


if __name__ == '__main__':
    pass
    # print(get_activity_lt('com.money.manager.ex.tutorial.TutorialActivity'))