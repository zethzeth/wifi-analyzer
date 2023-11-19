import time

import helpers.date_helpers as date_helpers
import helpers.print_helpers as print_helpers
from config import config


def prompt_for_settings():
    print_helpers.print_block_title('Prompting for details', 'blue', 0, 0)
    # Prompt for running speedtests
    run_speedtests = input("Run speedtests? (y/n): ").strip().lower() != "n"
    config["run_speedtests"] = run_speedtests

    # Prompt for the number of test rounds
    test_seconds_input = input("Duration to test in (seconds): ").strip()
    try:
        test_duration = int(test_seconds_input)
        config["test_duration"] = test_duration
    except ValueError:
        test_duration = config["test_duration"]

    # Start time
    test_start_unix_stamp = int(time.time())
    test_end_unix_stamp = test_start_unix_stamp + test_duration
    config['test_start_unix_stamp'] = test_start_unix_stamp
    config['test_end_unix_stamp'] = test_end_unix_stamp

    # Name
    # test_name = input("Test name: ").strip()
    # if not test_name:
    #     test_name = date_helpers.get_current_datetime_string() + '--duration-' + str(test_duration)
    # config["test_name"] = test_name

    test_name = date_helpers.get_current_datetime_string() + '--duration-' + str(test_duration)
    config["test_name"] = test_name
