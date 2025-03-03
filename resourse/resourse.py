import re
import subprocess
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist, squareform, cdist
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


def get_pid(package_name, device_name=None):
    if not device_name:
        command = f'adb shell ps | findstr {package_name}'
    else:
        command = f'adb -s {device_name} shell ps | findstr {package_name}'
    try:
        result = run_adb_command(command).split()
        if len(result) > 1:
            return result[1]
        else:
            return ''
    except:
        return ''


# 收集特定对象的数量
def get_object_counts(package_name, device_name=None):
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
    if not device_name:
        proc = subprocess.Popen("adb shell dumpsys meminfo " + package_name,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    else:
        proc = subprocess.Popen(f"adb -s {device_name} shell dumpsys meminfo " + package_name,
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


def get_java_heap(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Java Heap"'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name} | findstr /c:"Java Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split()[-2])
    return 0


def get_native_heap(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name} | findstr /c:"Native Heap"'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name} | findstr /c:"Native Heap"'
    result = run_adb_command(command)
    if result:
        return int(result.split('\n')[-1].split()[-2])
    return 0


def get_rss(package_name, device_name=None):
    if not device_name:
        command = f'adb shell dumpsys meminfo {package_name}'
    else:
        command = f'adb -s {device_name} shell dumpsys meminfo {package_name}'
    result = run_adb_command(command)
    match = re.search(r"TOTAL RSS:\s*(\d+)", result)
    if match:
        return int(match.group(1))
    return 0


def get_cpu(package_name, device_name=None):
    total_cpu = 0.0
    pid = get_pid(package_name, device_name)
    if pid == '':
        return total_cpu
    if not device_name:
        command = f'adb shell top -p {pid} -n 1'
    else:
        command = f'adb -s {device_name} shell top -p {pid} -n -1'
    result = run_adb_command(command).split('\n')
    for r in result:
        if "user" in r:
            items = r.split(" ")
            for item in items:
                if "user" in item:
                    parts = item.split("%")
                    return int(parts[0])
    return total_cpu


def get_fd_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != '':
        if not device_name:
            command = f'adb shell ls -l /proc/{pid}/fd | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell ls -l /proc/{pid}/fd | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_database_number(package_name, device_name=None):
    if not device_name:
        command = f'adb shell lsof | findstr {package_name} | findstr .db | find /v /c ""'
    else:
        command = f'adb -s {device_name} shell lsof | findstr {package_name} | findstr .db | find /v /c ""'
    result = run_adb_command(command)
    return int(result)


def get_wake_lock_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != '':
        if not device_name:
            command = f'adb shell dumpsys power | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell dumpsys power | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_camera_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell dumpsys media.camera | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell dumpsys media.camera | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_location_listener_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell dumpsys location | findstr {pid} | findstr Listener | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell dumpsys location | findstr {pid} | findstr Listener | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_media_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell dumpsys media.audio_flinger | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} dumpsys media.audio_flinger | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_sensor_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell dumpsys sensorservice | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell dumpsys sensorservice | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_socket_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell lsof | findstr {pid} | findstr socket | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell lsof | findstr {pid} | findstr socket | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_wifi_number(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid != "":
        if not device_name:
            command = f'adb shell lsof | findstr wifi | findstr {pid} | find /v /c ""'
        else:
            command = f'adb -s {device_name} shell lsof | findstr wifi | findstr {pid} | find /v /c ""'
        result = run_adb_command(command)
        return int(result)
    return 0


def get_services(package_name, device_name=None):
    services = set()
    if not device_name:
        command = f"adb shell dumpsys activity services {package_name} | findstr ServiceRecord"
    else:
        command = f"adb -s {device_name} shell dumpsys activity services {package_name} | findstr ServiceRecord"
    result = run_adb_command(command).split('\n')
    for r in result:
        services.add(r.split('/')[-1][:-1])
    return len(services)


def get_broadcast_receiver(package_name, device_name=None):
    broadcasts = set()
    if not device_name:
        command = f"adb shell dumpsys activity broadcasts | findstr {package_name}"
    else:
        command = f"adb -s {device_name} shell dumpsys activity broadcasts | findstr {package_name}"
    result = run_adb_command(command).split('\n')
    for r in result:
        r = r.strip()
        if r[0] == '#':
            broadcasts.add(r.split('/')[-1].split(' ')[0])
    return len(broadcasts)


def get_providers(package_name, device_name=None):
    providers = set()
    if not device_name:
        command = f"adb shell dumpsys activity providers | findstr {package_name}"
    else:
        command = f"adb -s {device_name} shell dumpsys activity providers | findstr {package_name}"
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


def multi_get_resource(package_name, device_name):
    resources = get_object_counts(package_name, device_name) if "object" in R else {}
    if "java heap" in R:
        resources["java heap"] = get_java_heap(package_name, device_name)
    if "native heap" in R:
        resources["native heap"] = get_native_heap(package_name, device_name)
    if "fd number" in R:
        resources["fd number"] = get_fd_number(package_name, device_name)
    if "db number" in R:
        resources["db number"] = get_database_number(package_name, device_name)
    if "wake lock number" in R:
        resources["wake lock number"] = get_wake_lock_number(package_name, device_name)
    # if "camera number" in R:
    #     resources["camera number"] = get_camera_number(package_name)
    # if "location listener number" in R:
    #     resources["location listener number"] = get_location_listener_number(package_name)
    # if "media number" in R:
    #     resources["media number"] = get_media_number(package_name)
    # if "sensor number" in R:
    #     resources["sensor number"] = get_sensor_number(package_name)
    if "socket number" in R:
        resources["socket number"] = get_socket_number(package_name, device_name)
    # if "wifi number" in R:
    #     resources["wifi number"] = get_wifi_number(package_name)
    if "cpu" in R:
        resources["cpu"] = get_cpu(package_name, device_name)
    if "rss" in R:
        resources["rss"] = get_rss(package_name, device_name)
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

def compute_multi_resource_sensitivity(resource1, resource2, weight):
    rewards = {}
    for key in resource1.keys():
        rewards[key] = weight[key] * compute_resource_sensitivity(resource1, resource2, key)
    return rewards


def init_resource(package_name):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        resources[k] = [v]
    return resources


def multi_init_resource(package_name, device_name):
    gc(package_name, device_name)
    resources = multi_get_resource(package_name, device_name)
    for k, v in resources.items():
        resources[k] = [v]
    return resources


def append_resource(package_name, pre_resource):
    gc(package_name)
    resources = get_resource(package_name)
    for k, v in resources.items():
        pre_resource[k].append(v)


def multi_append_resource(package_name, pre_resource, device_name):
    gc(package_name, device_name)
    resources = multi_get_resource(package_name, device_name)
    for k, v in resources.items():
        pre_resource[k].append(v)


def judge_resource(resources):
    analyze_resources(resources)


def gc(package_name, device_name=None):
    pid = get_pid(package_name, device_name)
    if pid == '':
        return
    if not device_name:
        command = f'adb shell kill -10 {pid}'
    else:
        command = f'adb -s {device_name} shell kill -10 {pid}'
    run_adb_command(command)


def classify_resources(data, prev_labels=None, num_clusters=3):
    """
    对资源进行层次聚类，并根据历史标签进行一致性检查。

    参数:
        data (dict): 输入字典，key 为资源名称，value 为时间序列数据 (list)。
        prev_labels (dict): 上一次的标签映射，key 为资源名称，value 为标签（数字）。
        num_clusters (int): 需要的聚类类别个数。

    返回:
        dict: 分类结果，key 为资源类型标签 (1, 2, 3...)，value 为资源名称列表。
        dict: 新的历史标签，key 为资源名称，value 为标签（数字）。
    """
    # Step 1: 修复平稳序列（避免相关性计算问题）
    for key in data.keys():
        if max(data[key]) == min(data[key]):
            data[key][0] = data[key][1] + 1

    # Step 2: 提取资源名称和特征值
    resource_names = list(data.keys())
    resource_values = np.array(list(data.values()))

    # Step 3: 计算相关性矩阵
    correlation_matrix = np.corrcoef(resource_values)

    # Step 4: 转换为距离矩阵 (1 - 相关性)
    distance_matrix = 1 - correlation_matrix
    condensed_distance_matrix = squareform(distance_matrix, checks=False)

    # Step 5: 层次聚类
    linkage_matrix = linkage(condensed_distance_matrix, method='average')

    # Step 6: 根据类别个数生成聚类结果
    cluster_labels = fcluster(linkage_matrix, t=num_clusters, criterion='maxclust')

    # Step 7: 将分类结果转为字典格式
    clusters = {}
    for i, label in enumerate(cluster_labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(resource_names[i])

    # Step 8: 为每个分组分配标签（数字标签，历史一致性检查）
    if prev_labels is None:
        prev_labels = {}  # 如果没有历史标签，则初始化为空字典

    new_labels = {}  # 保存新的标签映射
    used_labels = set(prev_labels.values())  # 已使用的历史标签
    next_label = max(used_labels) + 1 if used_labels else 1  # 下一个可用数字标签

    for cluster_id, resources in clusters.items():
        # Step 8.1: 统计当前组的历史标签
        label_counts = {}
        for resource in resources:
            if resource in prev_labels:
                label = prev_labels[resource]
                label_counts[label] = label_counts.get(label, 0) + 1

        # Step 8.2: 如果存在历史标签，选择出现次数最多的标签
        if label_counts:
            # 找到出现次数最多的历史标签
            most_common_label = max(label_counts, key=label_counts.get)
        else:
            # 如果没有历史标签，分配一个新标签
            most_common_label = next_label
            next_label += 1  # 更新下一个可用数字标签

        # Step 8.3: 更新新的标签映射
        for resource in resources:
            new_labels[resource] = most_common_label

    # Step 9: 按标签重新整理分组
    final_clusters = {}
    for resource, label in new_labels.items():
        if label not in final_clusters:
            final_clusters[label] = []
        final_clusters[label].append(resource)

    # 返回分类结果和新的历史标签
    return final_clusters, new_labels


if __name__ == "__main__":
    print(get_rss("com.tombursch.kitchenowl"))
