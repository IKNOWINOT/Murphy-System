import os
import subprocess

TASK_FILE = "TASK_INSTRUCTIONS.txt"

if not os.path.exists(TASK_FILE):
    raise SystemExit("No task instructions found.")

with open(TASK_FILE, "r") as f:
    instructions = f.read()

# Write instructions into a file so you can see them
with open("AGENT_OUTPUT.txt", "w") as f:
    f.write(instructions)

# Commit the output
subprocess.run(["git", "config", "user.name", "github-actions"])
subprocess.run(["git", "config", "user.email", "github-actions@github.com"])
subprocess.run(["git", "add", "AGENT_OUTPUT.txt"])
subprocess.run(["git", "commit", "-m", "Agent output"])
