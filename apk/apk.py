import os
import subprocess
import xml.etree.ElementTree as ET


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def install_apk(apk_path):
    command = f'adb install {apk_path}'
    result = run_adb_command(command)
    assert 'Success' in result, "Failed to install APK"


def install_apks(apk_path, devices):
    for device in devices:
        command = f'adb -s {device} install {apk_path}'
        run_adb_command(command)



def uninstall_app(package_name):
    command = f'adb uninstall {package_name}'
    result = run_adb_command(command)
    assert 'Success' in result, "Failed to uninstall APK"


def uninstall_apps(package_name, devices):
    for device in devices:
        command = f'adb -s {device} uninstall {package_name}'
        run_adb_command(command)


def apktool(apk_path):
    print('开始执行apktool')
    command = f'apk\\apktool d {apk_path} -o {apk_path.split(".")[0]}'
    result = run_adb_command(command)
    if result != '':
        print("Apktool successfully.")
    else:
        print(f"Apktool failed: {result}")


def xml_to_dict(element):
    node_dict = {}
    for child in element:
        child_dict = xml_to_dict(child)
        if child.tag not in node_dict:
            node_dict[child.tag] = child_dict
        else:
            if not isinstance(node_dict[child.tag], list):
                node_dict[child.tag] = [node_dict[child.tag]]
            node_dict[child.tag].append(child_dict)
    if element.attrib:
        node_dict["@attributes"] = element.attrib
    if element.text and element.text.strip():
        node_dict["@text"] = element.text.strip()

    return node_dict or None


def parse_xml_to_dict(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    return {root.tag: xml_to_dict(root)}


def component_extract(xml_file):
    xml = parse_xml_to_dict(xml_file)
    activities = []
    Main_activity = ''
    for activity in xml['manifest']['application']['activity']:
        activities.append(activity['@attributes']['{http://schemas.android.com/apk/res/android}name'])
        if 'android.intent.action.MAIN' in str(activity):
            Main_activity = activities[-1]
    package = xml['manifest']['@attributes']['package']
    return package, Main_activity, activities


def filtrate_code(lines):
    # 该文件的代码行数
    sum = lines.__len__()
    # 空行统计
    blank_count = 0
    # 单行注释统计
    line_count = 0
    # 多行注释统计的临时存储变量
    lines_temp_count = 0
    # 多行注释统计
    lines_count = 0
    # 多行注释的范围
    flag = False
    # 导包行
    package_count = 0

    # 遍历每一行
    for line in lines:
        # 空行判读
        if line in ['\n', '\r\n']:
            blank_count += 1

        # 单行注释判断
        if line.strip().startswith("//"):
            line_count += 1

        # 多行注释判断
        if flag:
            lines_temp_count += 1

        # 多行注释起始判断
        if line.strip().startswith("/**"):
            # 统计赋值为1
            lines_temp_count = 1
            # 多行注释开启
            flag = True

        # 多行注释结尾判断
        if line.strip().startswith("*/"):
            # 将临时统计赋值给lines_count
            lines_count += lines_temp_count
            # 关闭多行注释开关
            flag = False
            # 重新赋值临时统计
            lines_temp_count = 0

        # 导包行统计
        if line.strip().startswith("package"):
            package_count += 1

    # 返回过滤后的代码行数
    return sum - blank_count - line_count - package_count - lines_count


def count_lines(directory, extensions=(".java", ".kt")):
    """
    遍历目录统计所有代码文件的有效代码行数（过滤掉注释和空行）。
    """
    total_lines = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extensions):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        total_lines += filtrate_code(lines)
                except:
                    pass
    return total_lines


if __name__ == '__main__':
    path = "D:\File\Android-Aging-Test-ss_test\paper\\app rource\org.totschnig.myexpenses_774_src"
    print(count_lines(path))
