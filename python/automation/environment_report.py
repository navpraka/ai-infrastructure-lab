"""Generate a basic infrastructure environment report."""

import os
import platform
import shutil
import socket


def bytes_to_gb(value: int) -> float:
    """Convert bytes to gigabytes."""
    return round(value / (1024**3), 2)


def main() -> None:
    """Collect and display basic system information."""
    print("=" * 60)
    print("AI Infrastructure Lab - Environment Report")
    print("=" * 60)

    print(f"Hostname          : {socket.gethostname()}")
    print(f"Operating System  : {platform.system()} {platform.release()}")
    print(f"Architecture      : {platform.machine()}")
    print(f"Python Version    : {platform.python_version()}")
    print(f"Current User      : {os.getenv('USER') or os.getenv('USERNAME')}")

    total, used, free = shutil.disk_usage("/")

    print(f"Disk Total (GB)   : {bytes_to_gb(total)}")
    print(f"Disk Used (GB)    : {bytes_to_gb(used)}")
    print(f"Disk Free (GB)    : {bytes_to_gb(free)}")

    print("=" * 60)


if __name__ == "__main__":
    main()