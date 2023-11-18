import os
import select
import sys
import time
from datetime import datetime
from pprint import pprint

import services.router_service as router_service
import services.speedtest_service as speedtest_service
from config import config
from helpers.print_helpers import (
    print_table_headers, print_block_title,
)
from services.dns_service import resolve_domain
from services.network_service import ping


def display_info():
    print_block_title("Router info")
    router_ip = router_service.get_router_ip()
    router_details = router_service.get_router_details()
    pprint(router_details)
    print("IP: " + router_ip)

    print_block_title('Test details')
    for key, value in config.items():
        if (key == 'test_start_unix_stamp' or key == 'test_end_unix_stamp'):
            human_readable_date = datetime.fromtimestamp(value)
            formatted_date = human_readable_date.strftime("%Y-%m-%d--%H-%M-%S")
            print(f"{key}: {value} ({formatted_date})")
        else:
            print(f"{key}: {value}")
    print(f"\n\n")


def run_analysis():
    analysis_data = config['analysis_data']

    print_table_headers(
        "Timestamp", "Type", "Result (ms)", "Target", "Succeeded", "SNR", "Channel"
    )
    test_loops_done = 1
    while True:
        test_loops_done += 1

        max_loops = config['maximum_test_cycles_to_run']
        if test_loops_done >= max_loops:
            if int(os.getenv('DEBUG_VERBOSITY')) > 10:
                print(
                    'maximum_test_cycles_to_run break sign reached! Loops done: ' + str(
                        test_loops_done) + ' and max_loops: ' + str(
                        max_loops))
            break

        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:  # If Enter is hit
            line = input()
            break

        # PINGS
        router_ip = router_service.get_router_ip()
        ping_router_time = ping("ping router", router_ip)
        analysis_data.add_ping([ping_router_time, 'router'])

        ping_google_time = ping("ping google", "8.8.8.8")
        analysis_data.add_ping([ping_google_time, 'google'])

        ping_dr_time = ping("ping dr", "dr.dk")
        analysis_data.add_ping([ping_dr_time, 'dr.dk'])

        # DNS
        resolve_google = resolve_domain('google.com')
        analysis_data.add_dns_resolve([resolve_google, 'google'])

        resolve_google = resolve_domain('dr.dk')
        analysis_data.add_dns_resolve([resolve_google, 'dr.dk'])

        # SPEED TESTS
        if config["run_speedtests"]:
            download_speed, upload_speed = speedtest_service.get_speeds()
            analysis_data.add_speedtest([download_speed, upload_speed])

        time.sleep(config['pause_between_tests'])

    # Print report after while loop is broken
    analysis_data.print_report()
