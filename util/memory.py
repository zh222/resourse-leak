import re
import subprocess
from util.component import run_adb_command


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
    object_counts['Total'] = sum(object_counts.values())
    return object_counts


def get_memory(package_name):
    proc = subprocess.Popen("adb shell dumpsys meminfo " + package_name,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    memoryInfo, errInfo = proc.communicate()
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)\s+\d+", memoryInfo.decode())

    if match:
        heap_alloc_value = int(match.group(1)) / 1024
        return heap_alloc_value
    return None


def get_pid(package_name):
    command = f'adb shell ps | findstr {package_name}'
    result = run_adb_command(command).split()
    if len(result) > 1:
        return result[1]
    else:
        return ''


def get_fd(package_name):
    pid = get_pid(package_name)
    if pid != '':
        command = f'adb shell ls -l /proc/{pid}/fd'
        result = run_adb_command(command).split('\n')
        return len(result)
    return 0


def get_database(package_name):
    database = {}
    command = f'adb shell dumpsys meminfo {package_name}'
    result = run_adb_command(command).split('\n')
    for r in result:
        if '/data/user' in r:
            r = r.strip().split()
            key = r[-1] if '/data/user' in r[-1] else r[-2] + ' ' + r[-1]
            if key not in database:
                database[key] = int(r[1])
            else:
                database[key] += int(r[1])
    return database


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


def get_resource(package_name):
    return {'memory': get_memory(package_name), 'object_count': get_object_counts(package_name),
            'fd': get_fd(package_name), 'database': get_database(package_name), 'cpu': get_cpu(package_name)}


def init_resource(package_name):
    gc(package_name)
    object_count_change = {}
    for k, v in get_object_counts(package_name).items():
        object_count_change[k] = [v]
    database = {}
    for k, v in get_database(package_name).items():
        database[k] = [v]
    return {'memory': [get_memory(package_name)], 'object_count': object_count_change,
            'fd': [get_fd(package_name)], 'database': database, 'cpu': [get_cpu(package_name)]}


def append_resource(package_name, pre_resource):
    gc(package_name)
    resource = get_resource(package_name)
    for res in pre_resource.keys():
        if res == 'object_count' or res == 'database':
            for k, v in resource[res].items():
                if k not in pre_resource[res]:
                    pre_resource[res][k] = [v]
                else:
                    pre_resource[res][k].append(v)
        else:
            pre_resource[res].append(resource[res])


def gc(package_name):
    pid = get_pid(package_name)
    if pid == '':
        return
    command = f'adb shell kill -10 {pid}'
    run_adb_command(command)


if __name__ == "__main__":
    iiii = init_resource('de.taz.android.app.free')
    print(iiii)
    append_resource('de.taz.android.app.free', iiii)
    print(iiii)
    # print(get_cpu("de.taz.android.app.free"))
