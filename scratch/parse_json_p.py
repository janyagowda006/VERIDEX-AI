import json
import re

with open("scratch/script_0.js", "r", encoding="utf-8") as f:
    js = f.read()

# Extract json string inside const P = {...};
m = re.search(r'const P\s*=\s*(\{.*?\});\s*(?:const|let|var|function|\n\s*//|\n\s*function)', js, re.DOTALL)
if not m:
    # Try finding starting with const P={ and matching brackets
    start = js.find('const P=') + len('const P=')
    end = js.find(';\nconst', start)
    if end == -1: end = js.find(';\nfunction', start)
    json_str = js[start:end]
else:
    json_str = m.group(1)

try:
    data = json.loads(json_str)
    print("Keys in P:", list(data.keys()))
    for key in data.keys():
        with open(f"scratch/page_{key}.html", "w", encoding="utf-8") as pf:
            pf.write(data[key])
        print(f"Saved scratch/page_{key}.html ({len(data[key])} chars)")
except Exception as e:
    print("Error parsing JSON:", e)
