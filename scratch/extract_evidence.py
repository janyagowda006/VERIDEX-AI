import re
import os

html_path = r"C:\Users\Gagan Deep\.gemini\antigravity\brain\57939d3a-c6a9-4f67-be18-eca37279a774\.user_uploaded\media_1790859439685.html"

with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Let's search for how pages are structured in the prototype HTML
print("Length of HTML:", len(content))

# Look for P["..."] or page definitions or script tags
script_matches = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
print(f"Found {len(script_matches)} script tags")

for i, script in enumerate(script_matches):
    print(f"Script {i} length: {len(script)}")
    if 'P[' in script or 'P.' in script or 'evidence' in script:
        print(f"Script {i} contains keywords")
        with open(f"scratch/script_{i}.js", "w", encoding="utf-8") as sf:
            sf.write(script)

# Also search for 'evidence' in HTML body or template tags
with open("scratch/evidence_matches.txt", "w", encoding="utf-8") as out:
    for m in re.finditer(r'evidence', content, re.IGNORECASE):
        start = max(0, m.start() - 200)
        end = min(len(content), m.end() + 500)
        out.write(f"--- MATCH at {m.start()} ---\n{content[start:end]}\n\n")

print("Wrote matches to scratch/")
