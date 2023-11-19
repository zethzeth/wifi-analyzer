import os
import re
import subprocess
from pprint import pprint


def ping(ip_to_ping):
    response_time = -1
    succeeded = 0

    if not ip_to_ping:
        return response_time, succeeded

    exception = None
    try:
        ping_count = 1
        output = subprocess.check_output(
            f"ping -c {ping_count} {ip_to_ping}",
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        # Extract ping time from output
        match = re.search("time=(\d+\.\d+) ms", output)
        if match:
            response_time = int(match.group(1).split(".")[0])
            succeeded = 1
    except subprocess.CalledProcessError as e:
        succeeded = 0
        response_time = -1
        exception = e

    if not succeeded:
        if os.getenv("DEBUG") and int(os.getenv("DEBUG_VERBOSITY")) > 5:
            pprint(exception)
            # print("Command execution failed!")
            # print(f"Command: {exception.cmd}")
            # print(f"Return code: {exception.returncode}")
            # print("Output/Error:")
            # print(exception.output)  # or print(e.stdout)

    return response_time, succeeded
