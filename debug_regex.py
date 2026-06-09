#!/usr/bin/env python3
import re

with open("src/siha/harness/mutator.py") as f:
    text = f.read()

# Find all session.query occurrences
matches = re.findall(r'session\.query\([^)]+\)', text)
with open("debug_output.txt", "w") as out:
    out.write(f"Found {len(matches)} session.query matches\n")
    for m in matches[:5]:
        out.write(f"  {m}\n")

# Test single-line regex
pattern = r'session\.query\(([^)]+)\)\.filter\(([^)]+)\)\.first\(\)'
test = "session.query(Prompt).filter(Prompt.id == mutation.target_id).first()"
result = re.sub(pattern, r'session.exec(select(\\1).where(\\2)).first()', test)
with open("debug_output.txt", "a") as out:
    out.write(f"\nTest input: {test}\n")
    out.write(f"Test output: {result}\n")
