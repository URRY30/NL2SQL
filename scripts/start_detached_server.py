from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\xuexi\Desktop\rencai1\backend\.venv\Scripts\python.exe")
OUT = ROOT / "runtime" / "server.out.log"
ERR = ROOT / "runtime" / "server.err.log"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out = OUT.open("ab")
    err = ERR.open("ab")
    process = subprocess.Popen(
        [str(PYTHON), "run_server.py"],
        cwd=str(ROOT),
        stdout=out,
        stderr=err,
        stdin=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )
    print(process.pid)


if __name__ == "__main__":
    main()
