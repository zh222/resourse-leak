import re
import subprocess
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.stats import linregress
R = {
    "object",
    "java heap",
    "native heap",
    "fd number",
    "db number",
    "wake lock number",
    "camera number",
    "location listener number",
    "media number",
    "sensor number",
    "socket number",
    "wifi number",
    "cpu",
    "rss",
}



def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def linear_regression_analysis(series):
    x = np.arange(len(series))
    slope, intercept, r_value, p_value, std_err = linregress(x, series)
    return slope, p_value, r_value


def analyze_resources(resources):
    """
    对每个资源计算斜率，P 值以及 R 值
    """
    flag = []
    for resource, value in resources.items():
        slope, p_value, r_value = linear_regression_analysis(value)
        resources[resource] = {
            'value': value,
            'slope': slope,
            'p_value': p_value,
            'r_value': r_value,
            'is_bug': bool(slope > 0 and p_value < 0.05)
        }
        if resources[resource]['is_bug']:
            flag.append(resource)
    resources['is_bug'] = flag


def get_pid(package_name):
    command = f'adb shell ps | findstr {package_name}'
    try:
        result = run_adb_command(command).split()
        if len(result) > 1:
            return result[1]
        else:
            return ''
    except:
        return ''


# 收集特定对象的数量
def get_object_counts(package_name):
    object_types = [
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
        "WebViews"
    ]
    proc = subprocess.Popen("adb shell dumpsys meminfo " + package_name,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    object_counts = {}
    for obj_type in object_types:
        match = re.search(rf'{obj_type}:\s+(\d+)', memoryInfo.decode())
        if match:
            object_counts[obj_type] = int(match.group(1))
        else:
            object_counts[obj_type] = 0
    return object_counts


def get_java_heap(package_name):
    command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Java Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split()[-2])
    return 0


def get_native_heap(package_name):
    command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Native Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split('\n')[-1].split()[-2])
    return 0


def get_rss(package_name):
    command = f'adb shell dumpsys meminfo {package_name}'
    result = run_adb_command(command)
    match = re.search(r"TOTAL RSS:\s*(\d+)", result)
    if match:
        return int(match.group(1))
    return 0


def get_cpu(package_name):
    total_cpu = 0.0
    pid = get_pid(package_name)
    if pid == '':
        return total_cpu
    command = f'adb shell top -p {pid} -n 1'
    result = run_adb_command(command).split('\n')
    for r in result:
        if "user" in r:
            items = r.split(" ")
            for item in items:
                if "user" in item:
                    parts = item.split("%")
                    return int(parts[0])
    return total_cpu


def get_fd_number(package_name):
    pid = get_pid(package_name)
    if pid != '':
        command = f'adb shell ls -l /proc/{pid}/fd | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_database_number(package_name):
    command = f'adb shell lsof | findstr {package_name} | findstr .db | find /v /c ""'
    result = run_adb_command(command)
    return int(result)


def get_wake_lock_number(package_name):
    pid = get_pid(package_name)
    if pid != '':
        command = f'adb shell dumpsys power | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_camera_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell dumpsys media.camera | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_location_listener_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell dumpsys location | findstr {pid} | findstr Listener | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_media_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell dumpsys media.audio_flinger | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_sensor_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell dumpsys sensorservice | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_socket_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell lsof | findstr {pid} | findstr socket | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_wifi_number(package_name):
    pid = get_pid(package_name)
    if pid != "":
        command = f'adb shell lsof | findstr wifi | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_services(package_name):
    services = set()
    command = f"adb shell dumpsys activity services {package_name} | findstr ServiceRecord"
    result = run_adb_command(command).split('\n')
    for r in result:
        services.add(r.split('/')[-1][:-1])
    return len(services)


def get_broadcast_receiver(package_name):
    broadcasts = set()
    command = f"adb shell dumpsys activity broadcasts | findstr {package_name}"
    result = run_adb_command(command).split('\n')
    for r in result:
        r = r.strip()
        if r[0] == '#':
            broadcasts.add(r.split('/')[-1].split(' ')[0])
    return len(broadcasts)


def get_providers(package_name):
    providers = set()
    command = f"adb shell dumpsys activity providers | findstr {package_name}"
    result = run_adb_command(command).split('\n')
    for r in result:
        if "ContentProviderRecord" in r:
            providers.add(r.split('/')[-1].split('}')[0])
    return len(providers)


def get_resource(package_name):
    resources = get_object_counts(package_name) if "object" in R else {}
    if "java heap" in R:
        resources["java heap"] = get_java_heap(package_name)
    if "native heap" in R:
        resources["native heap"] = get_native_heap(package_name)
    if "fd number" in R:
        resources["fd number"] = get_fd_number(package_name)
    if "db number" in R:
        resources["db number"] = get_database_number(package_name)
    if "wake lock number" in R:
        resources["wake lock number"] = get_wake_lock_number(package_name)
    # if "camera number" in R:
    #     resources["camera number"] = get_camera_number(package_name)
    # if "location listener number" in R:
    #     resources["location listener number"] = get_location_listener_number(package_name)
    # if "media number" in R:
    #     resources["media number"] = get_media_number(package_name)
    # if "sensor number" in R:
    #     resources["sensor number"] = get_sensor_number(package_name)
    if "socket number" in R:
        resources["socket number"] = get_socket_number(package_name)
    # if "wifi number" in R:
    #     resources["wifi number"] = get_wifi_number(package_name)
    if "cpu" in R:
        resources["cpu"] = get_cpu(package_name)
    if "rss" in R:
        resources["rss"] = get_rss(package_name)
    for k, v in resources.items():
        if v == 0:
            resources[k] = 1
    return resources


def compute_resource_sensitivity(resource1, resource2, resource_type):
    return 1000 * (resource2[resource_type] - resource1[resource_type]) / resource1[resource_type]

def compute_resource_sensitivitis(resource1, resource2, resource_type_weight):
    reward = 0
    for key, value in resource1.items():
        reward += resource_type_weight[key] * (resource2[key] - resource1[key]) / value
    return 1000 * reward

def compute_multi_resource_sensitivity(resource1, resource2, resource_types):
    res = {}
    for resource_type, resources in resource_types.items():
        res[resource_type] = sum([compute_resource_sensitivity(resource1, resource2, resource) for resource in resources])
    return res


def init_resource(package_name):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        resources[k] = [v]
    return resources


def append_resource(package_name, pre_resource):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        pre_resource[k].append(v)


def judge_resource(resources):
    analyze_resources(resources)
    # if p_value <= 0.01 and slope > 0:
    #     print("P_value <= 0.01，判断为有bug")
    #     return "h", res, 500 * slope * (1 - p_value)
    # elif p_value < 0.05 and slope > 0:
    #     if number == 30:
    #         print("0.01 < P_value <= 0.05，不太显著，继续执行")
    #     else:
    #         print("执行多次P值不减，判断为有bug")
    #     return "m", res, 500 * slope * (1 - p_value)
    # else:
    #     print("P > 0.05, 不显著，判断为无bug")
    #     return "l", [], 500 * slope * (1 - p_value)


def gc(package_name):
    pid = get_pid(package_name)
    if pid == '':
        return
    command = f'adb shell kill -10 {pid}'
    run_adb_command(command)


def classify_resources_by_correlation(data, n_clusters):
    """
    使用层次聚类对资源进行分类，基于资源时间序列的相关性。
    参数:
        data (dict): 输入数据字典，key是资源名称，value是时间序列（list或numpy数组）。
        n_clusters (int): 需要分的类别数量。
    返回:
        dict: 分类结果，key是类别ID，value是资源名称列表。
    """
    # 将数据转换为 DataFrame
    data_df = pd.DataFrame(data)

    # 计算资源之间的相关性矩阵（皮尔逊相关性）
    correlation_matrix = data_df.corr(method='pearson')

    # 保留列名（资源名称）
    resource_names = correlation_matrix.columns

    # 层次聚类, 使用 1 - 相关性值作为距离
    correlation_matrix = np.nan_to_num(correlation_matrix.values, nan=0.0, posinf=1.0, neginf=-1.0)
    linkage_matrix = linkage(1 - correlation_matrix, method='average')

    # 根据聚类结果划分资源类别
    clusters = fcluster(linkage_matrix, t=n_clusters, criterion='maxclust')

    # 构造分类结果字典
    cluster_dict = {}
    for resource, cluster_id in zip(resource_names, clusters):
        if cluster_id not in cluster_dict:
            cluster_dict[cluster_id] = []
        cluster_dict[cluster_id].append(resource)

    return cluster_dict


if __name__ == "__main__":
    print(get_rss("com.tombursch.kitchenowl"))
