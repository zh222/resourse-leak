
from util.component import run_adb_command


def toggle_wifi(driver):
    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "wifi_on", "1"]
    })
    # 等待一段时间确保Wi-Fi已打开
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "wifi_on", "0"]
    })
    # 等待一段时间确保Wi-Fi已关闭
    driver.implicitly_wait(5)


def toggle_location_services(driver):
    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "secure", "location_providers_allowed", "+gps,network"]
    })
    # 等待一段时间确保位置服务已开启
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "secure", "location_providers_allowed", "-gps,network"]
    })
    # 等待一段时间确保位置服务已关闭
    driver.implicitly_wait(5)


def toggle_nfc(driver):
    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "nfc_enabled", "1"]
    })
    # 等待一段时间确保NFC已开启
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "nfc_enabled", "0"]
    })
    # 等待一段时间确保NFC已关闭
    driver.implicitly_wait(5)


def toggle_airplane_mode(driver):
    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "airplane_mode_on", "1"]
    })
    driver.execute_script("mobile: shell", {
        "command": "am",
        "args": ["broadcast", "-a", "android.intent.action.AIRPLANE_MODE"]
    })
    # 等待一段时间确保飞行模式已开启
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "airplane_mode_on", "0"]
    })
    driver.execute_script("mobile: shell", {
        "command": "am",
        "args": ["broadcast", "-a", "android.intent.action.AIRPLANE_MODE"]
    })
    # 等待一段时间确保飞行模式已关闭
    driver.implicitly_wait(5)


def toggle_data_sync(driver):
    driver.execute_script("mobile: shell", {
        "command": "content",
        "args": ["insert", "--uri", "content://settings/system", "--bind", "name:s:sync_auto", "--bind", "value:i:1"]
    })
    # 等待一段时间确保数据同步已开启
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "content",
        "args": ["delete", "--uri", "content://settings/system", "--where", "name='sync_auto'"]
    })
    # 等待一段时间确保数据同步已关闭
    driver.implicitly_wait(5)


def toggle_bluetooth(driver):
    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "bluetooth_on", "1"]
    })
    # 等待一段时间确保蓝牙已开启
    driver.implicitly_wait(5)

    driver.execute_script("mobile: shell", {
        "command": "settings",
        "args": ["put", "global", "bluetooth_on", "0"]
    })
    # 等待一段时间确保蓝牙已关闭
    driver.implicitly_wait(5)


def open_service(package_name, service_name):
    command = f'adb shell am startservice -n {package_name}/{service_name}'
    run_adb_command(command)


def close_service(package_name, service_name):
    command = f'adb shell am stopservice -n {package_name}/{service_name}'
    run_adb_command(command)


def open_receiver(package_name, receiver_name, action):
    command = f'adb shell am broadcast -a {action} -n {package_name}/{receiver_name}'
    run_adb_command(command)

