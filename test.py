from pyhprof.parsers import HProfParser

# 打开并解析 Hprof 文件
filename = 'heap-dump-converted.hprof'
with open(filename, 'rb') as file:
    # 创建 HProfParser 实例
    parser = HProfParser(file)

    # 遍历堆数据块
    leak_candidates = []  # 用来存储潜在的内存泄漏对象
    while True:
        block = parser.read_next_block()  # 读取下一个数据块
        if block is None:
            break

        # 假设我们想要分析某一类对象的内存泄漏，比如 Activity
        if block.class_name == 'android.app.Activity':
            if block.size > 1000:  # 如果某个 Activity 对象的内存占用大于 1000 字节
                leak_candidates.append(block)

    # 输出可能的内存泄漏对象
    for candidate in leak_candidates:
        print(f'可能的内存泄漏对象：{candidate.class_name}，对象 ID：{candidate.obj_id}，大小：{candidate.size} 字节')
