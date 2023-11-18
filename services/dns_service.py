import subprocess
import time

from helpers.date_helpers import get_current_datetime_string
from helpers.print_helpers import (
    print_table_ping_line,
)


def resolve_domain(domain_to_resolve):
    start_time = time.time()
    try:
        output = subprocess.check_output(
            ["dig", domain_to_resolve], stderr=subprocess.STDOUT, text=True
        )
        elapsed_time = int((time.time() - start_time) * 1000)  # milliseconds

        # Check for "ANSWER SECTION" in the output
        if "ANSWER SECTION" in output:
            succeeded = 1
        else:
            succeeded = 0
            elapsed_time = -1

    except subprocess.CalledProcessError:
        succeeded = 0
        elapsed_time = -1

    print_table_ping_line(
        get_current_datetime_string("%H:%M:%S"),
        "dig " + domain_to_resolve,
        elapsed_time,
        domain_to_resolve,
        succeeded,
        " ",
        " ",
    )
    return elapsed_time
