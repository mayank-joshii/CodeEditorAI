import subprocess
import sys

proc = subprocess.Popen(
    ["python3", "user_code.py"],
    stdin=sys.stdin,
    stdout=sys.stdout,
    stderr=sys.stderr,
)

proc.communicate()
