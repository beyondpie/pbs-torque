import sys

restart_times = "{{cookiecutter.restart_times}}"
try:
    restart_times = int(restart_times)
    if restart_times < 0:
        raise ValueError
except ValueError:
    print(f"restart_times ({restart_times}) must be a non-negative integer.")
    sys.exit(1)

latency_wait = "{{cookiecutter.latency_wait}}"
try:
    latency_wait = float(latency_wait)
    if latency_wait < 0:
        raise ValueError
except ValueError:
    print(f"latency_wait ({latency_wait}) must be a non-negative float.")
    sys.exit(1)
