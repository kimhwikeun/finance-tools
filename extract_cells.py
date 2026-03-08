import json
import os

with open(r'g:\My Drive\AI\finance-tools\screeners\Dual_AI_Stock_Analyzer.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i in [10, 11]:
    with open(f'cell_{i}.py', 'w', encoding='utf-8') as out:
        out.write(''.join(nb['cells'][i]['source']))
