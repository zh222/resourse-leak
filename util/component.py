import subprocess


def run_adb_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_activity_stack(package_name):
    activities = set()
    command = f'adb shell dumpsys activity activities | findstr /C:"* ActivityRecord" | findstr {package_name}'
    result = run_adb_command(command).split('\n')
    for r in result:
        activities.add(r.split('/')[-1].split(' ')[0])
    return list(activities)


def get_top_fragments():
    fragments = set()
    command = "adb shell dumpsys activity top | findstr #[0-9]:"
    result = run_adb_command(command).split('\n')
    for r in result:
        if 'ReportFragment{' in r:
            fragments.add(r.split(' ')[-1][:-1])
    return list(fragments)


def get_services(package_name):
    services = set()
    command = f"adb shell dumpsys activity services {package_name} | findstr ServiceRecord"
    result = run_adb_command(command).split('\n')
    for r in result:
        services.add(r.split('/')[-1][:-1])
    return list(services)


def get_broadcasts(package_name):
    broadcasts = set()
    command = f"adb shell dumpsys activity broadcasts | findstr {package_name}"
    result = run_adb_command(command).split('\n')
    for r in result:
        r = r.strip()
        if r[0] == '#':
            broadcasts.add(r.split('/')[-1].split(' ')[0])
    return list(broadcasts)


def get_providers(package_name):
    command = f"adb shell dumpsys content providers | findstr {package_name}"
    result = run_adb_command(command)
    return result


if __name__ == '__main__':
    # print(get_activity_stack('de.taz'))
    # print(get_top_fragments())
    # print(get_services('de.taz.android.app.free'))
    print(get_broadcasts('de.taz.android.app.free'))
    print(get_providers('de.taz.android'))
