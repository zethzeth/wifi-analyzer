import subprocess
import time

from helpers.date_helpers import get_current_datetime_string
from helpers.print_helpers import (
    print_table_ping_line,
)


def resolve_domain():
    start_time = time.time()
    test_domain = 'google.com'
    succeeded = 1
    try:
        subprocess.check_output(
            ["dig", test_domain], stderr=subprocess.STDOUT, text=True
        )
        elapsed_time = int((time.time() - start_time) * 1000)  # milliseconds
        # db.add_log_to_db("dns resolution", elapsed_time, test_domain, succeeded)

        print_table_ping_line(
            get_current_datetime_string("%H:%M:%S"),
            "DNS resolution",
            elapsed_time,
            test_domain,
            succeeded,
            " ",
            " ",
        )

        return elapsed_time
    except subprocess.CalledProcessError:
        succeeded = 0

        print_table_ping_line(
            get_current_datetime_string("%H:%M:%S"),
            "DNS resolution",
            None,
            test_domain,
            succeeded,
            " ",
            " ",
        )
        # db.add_log_to_db("dns resolution", None, test_domain, succeeded)
        return 0
