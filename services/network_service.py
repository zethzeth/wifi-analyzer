import os
import time
import subprocess
import re

from helpers.date_helpers import get_current_datetime_string
from helpers.print_helpers import (
    print_table_ping_line,
)

from database import db


def ping(event_type, ip_to_ping):
    succeeded = 1
    try:
        ping_count = os.getenv("PING_COUNT")
        output = subprocess.check_output(
            f"ping -c {ping_count} {ip_to_ping}",
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        # Extract ping time from output
        match = re.search("time=(\d+\.\d+) ms", output)
        if match:
            response_time = match.group(1).split(".")[0]
            print_tests = os.getenv("PRINT_TESTS")
            if print_tests:
                print_table_ping_line(
                    get_current_datetime_string("%H:%M:%S"),
                    event_type,
                    response_time,
                    ip_to_ping,
                    succeeded,
                )
            db.add_log_to_db(event_type, response_time, ip_to_ping, succeeded)
            return True
    except subprocess.CalledProcessError:
        succeeded = 0
        response_time = None

        print_tests = os.getenv("PRINT_TESTS")
        if print_tests:
            print_table_ping_line(
                get_current_datetime_string("%H:%M:%S"),
                event_type,
                response_time,
                ip_to_ping,
                succeeded,
            )
        db.add_log_to_db(event_type, None, ip_to_ping, succeeded)
        return False
