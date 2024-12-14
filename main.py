import csv
import os
import time
import json
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from aut_env import AndroidAppEnv
from Algorithm.Q import QLearningAgent
from Algorithm.Random import RandomAgent
from stable_baselines3 import SAC
from apk.apk import install_apk, uninstall_app, apktool, component_extract


def run(al, number, app, apk_path):
    global agent, env
    install_apk(f'apk/{apk_path}')
    package, Main_activity, activities, services, receivers, providers = component_extract(
        f'apk/{apk_path}/AndroidManifest.xml')
    res = [0, 0, 0, 0]
    # try:
    if al == 'q':
        env = AndroidAppEnv(package, Main_activity, 'mem', activities, services, receivers, providers)
        agent = QLearningAgent(env)
        agent.learn(number)
    elif al == 'sac_cov':
        env = AndroidAppEnv(package, Main_activity, 'cov', activities, services, receivers, providers)
        agent = SAC("MultiInputPolicy", env, verbose=1, train_freq=5, target_update_interval=10, buffer_size=1000)
        agent.learn(total_timesteps=number, log_interval=4)
    elif al == 'sac_mem':
        env = AndroidAppEnv(package, Main_activity, 'mem', activities, services, receivers, providers)
        agent = SAC("MultiInputPolicy", env, verbose=1, train_freq=5, target_update_interval=10, buffer_size=1000)
        agent.learn(total_timesteps=number, log_interval=4)
    elif al == 'random':
        env = AndroidAppEnv(package, Main_activity, 'cov', activities, services, receivers, providers)
        agent = RandomAgent(env)
        agent.learn(number)
    try:
        os.kill(env.bug_proc_pid, 9)
    except:
        pass
    res = [len(env.bug_report), len(env.list_activities), len(env.state), len(env.done_test)]
    if not os.path.exists(f'result/{app}'):
        os.mkdir(f'result/{app}')
    agent.save(f"result/{app}/{al}_{number}")
    with open(f'result/{app}/{al}_bug_report.json', 'w', encoding='utf-8') as json_file:
        json.dump(env.bug_report, json_file, ensure_ascii=False, indent=4)
    with open(f'result/{app}/{al}_coverage.csv', 'w', newline='', encoding='utf-8') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['bugs', f'activities/{len(activities)}', 'states', 'neutral_number'])
        csv_writer.writerow([len(env.bug_report), len(env.list_activities), len(env.state), len(env.done_test)])
    with open(f'result/{app}/{al}_aging_metric.csv', 'w', newline='', encoding='utf-8') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['memory', 'aging_metric'])
        for i in range(len(env.aging_metric)):
            csv_writer.writerow([env.memory[i], env.aging_metric[i]])
    with open(f'result/{app}/{al}_state_number.csv', 'w', newline='', encoding='utf-8') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['遍历到的次数', '内存上升次数'])
        for v in env.state.values():
            csv_writer.writerow([v[1], v[2]])
    with open(f'result/{app}/{al}_broken_bug.json', 'w', encoding='utf-8') as json_file:
        json.dump(env.bug_queue, json_file, ensure_ascii=False, indent=4)
    # except Exception as e:
    #     print(f"{al}_{app}_训练时出错了")
    #     print(e)
    try:
        uninstall_app(package)
        env.close()
    except:
        pass
    return res


def main():

    data = {k_apps: {k_als: [] for k_als in als} for k_apps in apps.keys()}
    for app, apk_path in apps.items():
        # apktool(apk_path)
        for al in als:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} start")
            res = run(al, number, app, apk_path)
            data[app][al] = res
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} {app} {al} stop")
    with open('result/result.csv', 'w', newline='', encoding='utf-8') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(['app_name', 'memory bugs', '', '', 'activity number', '', '', 'state number', '', ''
                             'neutral number', '', ''])
        csv_writer.writerow([''] + als * 4)
        for app, res in data.items():
            csv_writer.writerow([app] + [res[als[j]][i] for i in range(len(res[als[0]])) for j in range(len(als))])


if __name__ == '__main__':
    als = [
        "sac_mem",
        "sac_cov",
        "random"
    ]
    apps = {
        # 'Daily Diary': ['com.voklen.daily_diary', 'com.voklen.daily_diary.MainActivity'],
        # 'Money Manager Ex': 'com.money.manager.ex_1045',
        # 'Kanji Dojo': ['ua.syt0r.kanji.fdroid', 'ua.syt0r.kanji.presentation.screen.main.FdroidMainActivity'],
        # 'SelfPrivacy': ['pro.kherel.selfprivacy', 'org.selfprivacy.app.MainActivity'],
        'taz': 'de.taz.android.app.free_10903900',
        # 'Baby book': ['com.serwylo.babybook', 'com.serwylo.babybook.MainActivity']
    }
    number = 2000
    main()
