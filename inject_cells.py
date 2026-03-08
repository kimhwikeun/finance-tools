import json

# Read the notebook
notebook_path = r'g:\My Drive\AI\finance-tools\screeners\Dual_AI_Stock_Analyzer.ipynb'
with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Read modified cells
for i in [10, 11]:
    with open(f'cell_{i}.py', 'r', encoding='utf-8') as f_in:
        code = f_in.read()
    
    # split by lines keeping the \n (Jupyter format for source arrays)
    lines = code.splitlines(keepends=True)
    nb['cells'][i]['source'] = lines

# Save back to notebook
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Successfully injected cells back into notebook.")
