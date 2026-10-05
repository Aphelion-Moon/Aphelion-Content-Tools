"""Start a native command only after the parent has assigned process ownership."""
from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
	if sys.stdin.buffer.read(1) != b'1':
		return 125
	command = json.loads(sys.argv[1])
	if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
		return 125
	return subprocess.call(command, stdin=subprocess.DEVNULL)


if __name__ == '__main__':
	raise SystemExit(main())
