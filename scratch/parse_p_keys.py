import re

with open("scratch/script_0.js", "r", encoding="utf-8") as f:
    js = f.read()

# Find keys in P object or P[...]
pages = re.findall(r'P\["([^"]+)"\]', js)
print("P[...] keys:", set(pages))

# Output P["evidence"] block to file
match = re.search(r'P\["evidence"\]\s*=\s*`([^`]+)`', js, re.DOTALL)
if match:
    with open("scratch/p_evidence.html", "w", encoding="utf-8") as out:
        out.write(match.group(1))
    print("Wrote scratch/p_evidence.html successfully!")
else:
    print("Could not find P[\"evidence\"] template string, searching alternate patterns...")
    # Maybe double quotes or single quotes or assignment?
    matches = re.findall(r'P\["evidence"\]\s*=\s*(.+?);', js, re.DOTALL)
    print(f"Found {len(matches)} alternate matches")
