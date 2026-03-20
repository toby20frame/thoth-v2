import sys
import time
import traceback
from coordinator import Coordinator


def run_once():
    coordinator = Coordinator()
    coordinator.run_cycle()


def run_loop(interval_seconds: int = 3600):
    print(f"Thoth starting — cycle interval: {interval_seconds}s")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Cycle failed: {e}", file=sys.stderr)
            traceback.print_exc()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = 3600
        for i, arg in enumerate(sys.argv):
            if arg == "--interval" and i + 1 < len(sys.argv):
                interval = int(sys.argv[i + 1])
        run_loop(interval)
    else:
        run_once()

