import subprocess
from time import time

def run(cmd: list[str]) -> None:
    print("\nRunning:")
    print(" ".join(map(str, cmd)))
    start = time()
    subprocess.run(cmd, check=True)
    print(f"Command f{cmd[0]} finished in {time()-start:.2f} seconds.")