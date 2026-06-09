#!/usr/bin/env python3
"""Run git commands and write output to a file."""
import subprocess
import sys

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd='/Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness')
    return f"CMD: {cmd}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nRETURN: {result.returncode}\n{'='*40}\n"

output = ""
output += run("git status --short")
output += run("git add -A")
output += run("git status --short")
output += run("git commit -m 'fix: comprehensive codebase safety and robustness fixes'")
output += run("git push")

with open("/tmp/git_actions.log", "w") as f:
    f.write(output)
print("done")
