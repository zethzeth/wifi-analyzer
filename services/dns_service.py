import os
import time
import subprocess
from database import db


def resolve_domain():
    start_time = time.time()
    test_domain = os.getenv("TEST_DOMAIN")
    succeeded = 1
    try:
        subprocess.check_output(
            ["dig", test_domain], stderr=subprocess.STDOUT, text=True
        )
        elapsed_time = int((time.time() - start_time) * 1000)  # milliseconds
        db.add_log_to_db("dns resolution", elapsed_time, test_domain, succeeded)
        return True
    except subprocess.CalledProcessError:
        succeeded = 0
        db.add_log_to_db("dns resolution", None, test_domain, succeeded)
        return False
