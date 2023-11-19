import subprocess
import time


def resolve_domain(domain_to_resolve):
    succeeded = 0
    elapsed_time = -1

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

    return elapsed_time, succeeded
