import os
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体为 SimHei（黑体）
rcParams['axes.unicode_minus'] = False   # 解决负号显示问题
import pandas as pd
import json
import time


als = [
        "q_cov",
        "random",
        "q_res_weight",
    ]
apps = os.listdir("result")
app_bugs = {key: {al: 0 for al in als} for key in apps}
app_states = {key: {al: 0 for al in als} for key in apps}


def plot_data(data, x_label="X轴", y_label="Y轴", title="图表"):
    x = list(range(len(data)))
    plt.figure(figsize=(8, 6))  # 设置图表大小
    plt.plot(x, data, marker="o", linestyle="-", color="b", label="")  # 折线图
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.savefig(f"taz_home.pdf", format="pdf")
    plt.legend()
    plt.show()


def plot_multiple_lists(list1, list2, list3, x_label="X轴", y_label="Y轴", title="多列表图像"):
    x = list(range(len(list1)))  # 假设横坐标为 0 到 len(list1)-1 的索引值
    plt.figure(figsize=(8, 6))  # 设置图表大小
    plt.plot(x, list1, label="resource_base", color="b")
    plt.plot(x, list2, label="coverage_base", color="g")
    plt.plot(x, list3, label="random", color="r")
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title("算法对比")
    plt.savefig(f"bug_number.pdf", format="pdf")
    plt.legend()
    plt.show()


def RQ1():
    # RQ1 旨在判断缺陷检测算法是否能找到明显的老化缺陷，即需要找到执行中性序列时 app 占用资源持续上升的情况
    for app_name in apps:  # app 列表
        for i in range(n):  # 实验重复次数
            for al in als:  # 算法列表
                try:
                    with open(f"result/{app_name}/{i + 1}/{al}_bug_report.json", "r") as fp:
                        data = json.load(fp)
                        for state, [bugs, t] in data.items():
                            for resource, bug in bugs.items():
                                if isinstance(bug, dict) and bug["is_bug"]:
                                    if resource == 'java heap' and state.split('_')[1] == 'doc':
                                        plot_data(bug['value'], '中性序列执行次数', resource, f"{app_name}_{state.split('_')[0]}_{state.split('_')[1]}")
                                        time.sleep(2)
                except:
                    pass


def RQ2():
    # RQ2 旨在判断论文算法找老化缺陷的能力，对比算法为基于覆盖率的强化学习以及随机算法，可以考虑比较找到 bug 的数量以及速度
    app_bugs = {app: {al: 0 for al in als} for app in apps}  # 用于保存三种算法在各个 app 上找到的缺陷数量
    for app_name in apps:  # app 列表
        for i in range(n):  # 实验重复次数
            for al in als:  # 算法列表
                with open(f"result/{app_name}/{i + 1}/{al}_bug_report.json", "r") as fp:
                    data = json.load(fp)
                    for state, [bugs, t] in data.items():
                        app_bugs[app_name][al] += len(bugs['is_bug'])
    print(app_bugs)
    al_speed = {al: [0 for i in range(8000)] for al in als}  # 用于保存三种算法找到 bug 的时间
    for app_name in apps:  # app 列表
        for i in range(n):  # 实验重复次数
            for al in als:  # 算法列表
                with open(f"result/{app_name}/{i + 1}/{al}_bug_report.json", "r") as fp:
                    data = json.load(fp)
                    for state, [bugs, t] in data.items():
                        if t <= 8000:
                            al_speed[al][int(t)] += len(bugs['is_bug'])
    for al in als:
        for i in range(1, len(al_speed[al])):
            al_speed[al][i] += al_speed[al][i - 1]
    plot_multiple_lists(al_speed['q_res_weight'], al_speed['q_cov'], al_speed['random'], '探索时间 t', '缺陷数量')


def RQ3():
    # RQ3 旨在研究老化缺陷的分布情况，看看是否不同 app/中性序列 发现的老化缺陷类别是不同分布的
    app_bug_type = {app: {} for app in apps}  # 用于收集各个 app 中存在的不同类型的缺陷个数
    neutral_bug_type = {}  # 用于收集各个中性序列中存在的不同类型的缺陷个数
    for app_name in apps:  # app 列表
        for i in range(n):  # 实验重复次数
            for al in als:  # 算法列表
                with open(f"result/{app_name}/{i + 1}/{al}_bug_report.json", "r") as fp:
                    data = json.load(fp)
                    for state, [bugs, t] in data.items():
                        neutral_type = state.split("_")[1]
                        if neutral_type not in neutral_bug_type:
                            neutral_bug_type[neutral_type] = {}
                        for bug in bugs['is_bug']:
                            if bug not in app_bug_type[app_name]:
                                app_bug_type[app_name][bug] = 1
                            else:
                                app_bug_type[app_name][bug] += 1
                            if bug not in neutral_bug_type[neutral_type]:
                                neutral_bug_type[neutral_type][bug] = 1
                            else:
                                neutral_bug_type[neutral_type][bug] += 1
    print(app_bug_type)
    print(neutral_bug_type)


def RQ4():
    # RQ4 旨在探讨随机性对算法的影响，以及不同算法之间的导向有什么差异。可以通过不同算法找到的 bug 差异与相同算法找到的 bug 差异来表示
    pass


if __name__ == "__main__":
    n = 2  # 实验重复次数
    RQ1()
    # RQ2()
    # RQ3()
    # RQ4()
