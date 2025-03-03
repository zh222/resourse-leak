# 该模块用于存储及修改多线程中所使用的全局变量
import threading


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
apps = {
    'taz': 'apk/middle/taz_43892.apk'
    }

N = 2


previous_centers = {}  # 聚类中心，用于一致性检查
category = {i + 1: [r for r in R] for i in range(N)}  # 资源类别
lock = threading.Lock()  # 线程锁，用于保护临界资源
q_tables = {r: {} for r in R}


def set_previous_centers_and_category(cg, centers):
    global previous_centers
    global category
    with lock:
        for c in category.keys():
            category[c] = cg[c]
        for c in previous_centers.keys():
            previous_centers[c] = centers[c]


def get_q_tables():
    global q_tables
    return q_tables


def get_category():
    global category
    return category


def get_previous_centers():
    global previous_centers
    return previous_centers


def init_q_tables(state, env):
    global q_tables
    with lock:
        for res in q_tables.keys():
            if state not in q_tables[res]:
                n = len(env.views)
                if n != 0:
                    q_tables[res][state] = {(i / n, 0, 0): 0 for i in range(n)}


def update_q_tables(state, action, res, learning_rate, td_error):
    global q_tables
    with lock:
        q_tables[res][state][action] += learning_rate * td_error
