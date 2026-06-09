#!/usr/bin/env python3
import subprocess

result = subprocess.run(
    ['git', 'status', '--short'],
    capture_output=True,
    text=True,
    cwd='/Users/manaskandimalla/Desktop/2026-Projects/Self-Improving-Harness'
)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("RC:", result.returncode)
