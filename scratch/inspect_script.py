with open("scratch/script_0.js", "r", encoding="utf-8") as f:
    js = f.read()

print("First 2000 chars of script:")
print(js[:2000])

import re
print("\n--- Search for evidence in script ---")
for m in re.finditer(r'evidence', js, re.IGNORECASE):
    start = max(0, m.start() - 100)
    end = min(len(js), m.end() + 200)
    print(js[start:end])
    print("="*40)
