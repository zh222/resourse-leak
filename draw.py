import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib_venn import venn3


def line():
    # 设置matplotlib支持中文显示（需要有相应的字体）
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体显示中文
    plt.rcParams['axes.unicode_minus'] = False    # 正常显示负号

    y_mem = pd.read_csv('result/taz/sac_mem_aging_metric.csv', usecols=[0, 1])['memory'].tolist()[:47]
    y_cov = pd.read_csv('result/taz/3/sac_cov_aging_metric.csv', usecols=[0, 1])['memory'].tolist()[:47]
    y_random = pd.read_csv('result/taz/3/random_aging_metric.csv', usecols=[0, 1])['memory'].tolist()[:47]
    x = [i for i in range(len(y_mem))]
    # 绘制图形
    plt.figure(figsize=(8, 6))

    # 绘制三条折线图，并指定颜色
    plt.plot(x, y_mem, color='blue', label='memory')      # 线1 - 蓝色
    plt.plot(x, y_cov, color='green', label='cov')     # 线2 - 绿色
    plt.plot(x, y_random, color='red', label='random')  # 线3 - 红色

    # 添加标题和轴标签
    plt.title('老化对比')
    plt.xlabel('轮次')
    plt.ylabel('memory')

    # 显示图例
    plt.legend()

    # 显示图形
    plt.show()


ac = []
for i in range(2, 4):
    with open(f'result/taz{i}/q_res_activities.csv') as f:
        ac.append(f.readlines())
with open('result/taz/q_res_activities.csv') as f:
    ac.append(f.readlines())
for i in range(len(ac)):
    ac[i] = set(ac[i])
ac = list(ac)
venn = venn3(ac, ('1', '2', '3'))
plt.title("venn Diagram")
plt.show()
