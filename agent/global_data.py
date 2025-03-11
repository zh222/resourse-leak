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
    "keepassDroid": "apk/middle/keepassDroid_25133.apk",
    "k9mail": "apk/high/k9mail_162720.apk",
    "newpipe": "apk/high/newpipe_57363.apk",
    "RunnerUp": "apk/middle/RunnerUp_30729.apk",
    "money_manager_ex": "apk/middle/money_manager_ex_41537.apk",
    "myexpenses": "apk/high/myexpenses_137437.apk",
    "redreader": "apk/high/redreader_62750.apk",
    "taz": "apk/middle/taz_43892.apk",
    "AntennaPod": "apk/middle/AntennaPod_23793.apk",
    "butterfly": "apk/low/butterfly_6043.apk",
    "selfprivacy": "apk/low/selfprivacy_6043.apk",
    "KitchenOwl": "apk/low/KitchenOwl_9664.apk",
    "neurolab": "apk/low/neurolab_8284.apk",
    "souvenirs": "apk/low/souvenirs_9206.apk",
    "tunner": "apk/low/tuner_3690.apk",
    "bitbanana": "apk/middle/bitbanana_39794.apk",

    "Gadgetbridge": "apk/high/Gadgetbridge_221736.apk",
    "Easter_Eggs": "apk/middle/Easter_Eggs_32771.apk",
    "News_Reader": "apk/low/News_Reader_7358.apk",
    "Activity_Manager": "apk/low/Activity_Manager_7383.apk",
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
