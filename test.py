import json


with open('result/taz/4/node_resources.json', 'r') as f:
    node_resources = json.load(f)
with open('result/taz/4/q_cov_bug_report.json', 'r') as f:
    q_cov_bug_report = json.load(f)

for q in q_cov_bug_report:
    q = q.split('_')[-1]
    temp = []
    for c in q:
        temp.append(c)
    print(node_resources[tuple(temp)])
print(1)

