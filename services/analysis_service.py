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
    summarized_ping = 0
    number_of_pings = 0
    failed_pings = 0

    summarized_dns_resolve_time = 0
    number_of_dns_resolves = 0
    failed_dns_resolves = 0

    summarized_download_speed = 0
    summarized_upload_speed = 0
    number_of_download_speedtests = 0
    number_of_upload_speedtests = 0

    def add_speedtest_values(download_speed, upload_speed):
        nonlocal summarized_download_speed, summarized_upload_speed, number_of_download_speedtests, number_of_upload_speedtests
        if download_speed != 0:
            summarized_download_speed += download_speed
            number_of_download_speedtests += 1
        if upload_speed != 0:
            summarized_upload_speed += upload_speed
            number_of_upload_speedtests += 1

    def add_ping_value(ping_time):
        nonlocal summarized_ping, number_of_pings, failed_pings
        if ping_time != 0:  # Check if ping was successful
            summarized_ping += ping_time
            number_of_pings += 1
        else:
            failed_pings += 1

    def add_dns_resolve_value(dns_resolve_time):
        nonlocal summarized_dns_resolve_time, number_of_dns_resolves, failed_dns_resolves
        if dns_resolve_time != 0:  # Check if ping was successful
            summarized_dns_resolve_time += dns_resolve_time
            number_of_dns_resolves += 1
        else:
            failed_dns_resolves += 1

    completed_test_runs = 0

    print_table_headers(
        "Timestamp", "Type", "Result (ms)", "Target", "Succeeded", "SNR", "Channel"
    )
    test_runs = 1
    while True:
        test_runs += 1
        completed_test_runs += 1
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = input()
            # Calculating averages
            if test_runs > 0:
                if number_of_pings > 0:
                    avg_ping_time = summarized_ping / number_of_pings
                    print(
                        f"Average ping time: {avg_ping_time:.2f} ms ({number_of_pings})"
                    )
                    print(f"Failed pings: {failed_pings}")
                else:
                    print(f"number_of_pings was 0")

                if number_of_dns_resolves > 0:
                    avg_dns_resolve_time = (
                            summarized_dns_resolve_time / number_of_dns_resolves
                    )
                    print(
                        f"Average DNS resolve time: {avg_dns_resolve_time:.2f} ms ({number_of_dns_resolves})"
                    )
                    print(f"Failed DNS resolves: {failed_dns_resolves}")
                else:
                    print(f"number_of_dns_resolves was 0")

                if number_of_download_speedtests > 0:
                    avg_download_speed = (
                            summarized_download_speed / number_of_download_speedtests
                    )
                    print(
                        f"Average download speed: {avg_download_speed:.2f} Mbps ({number_of_download_speedtests})"
                    )
                else:
                    print(
                        f"number_of_download_speedtests was 0. Sum: {summarized_download_speed}"
                    )
                if number_of_upload_speedtests > 0:
                    avg_upload_speed = (
                            summarized_upload_speed / number_of_upload_speedtests
                    )
                    print(
                        f"Average upload speed: {avg_upload_speed:.2f} Mbps ({number_of_upload_speedtests})"
                    )
                else:
                    print(
                        f"number_of_upload_speedtests was 0. Sum: {summarized_upload_speed}"
                    )
            else:
                print("No tests were completed.")
            break

        # PINGS
        ping_router = ping("ping router", router_service.get_router_ip())
        add_ping_value(ping_router)

        ping_google = ping("ping google", "8.8.8.8")
        add_ping_value(ping_google)

        ping_dr = ping("ping dr", "dr.dk")
        add_ping_value(ping_dr)

        # DNS
        resolve_google = resolve_domain()
        add_dns_resolve_value(resolve_google)

        # SPEED TESTS
        if config["run_speedtests"]:
            download_speed, upload_speed = speedtest_service.get_speeds()
            summarized_download_speed += download_speed
            summarized_upload_speed += upload_speed

        pause_interval = 1
        time.sleep(pause_interval)
