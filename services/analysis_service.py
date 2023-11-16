import os
import select
import time
import sys
import speedtest

from pprint import pprint
from helpers.concurrent_helpers import run_concurrently
from helpers.date_helpers import get_current_datetime_string
from helpers.print_helpers import (
    print_formatted,
    print_block_title,
    print_table_headers,
    print_table_ping_line,
)
from config import config

from database.db import get_connection
from core.analysis_state import AnalysisState

from services.network_service import ping
from services.dns_service import resolve_domain
from services.router_service import get_router_ip, get_router_details


def start_new_analysis():
    print_block_title("Starting analysis")

    # Router info
    router_ip = get_router_ip()
    router_details = get_router_details()
    print_block_title("Router info")
    pprint(router_details)
    print("IP: " + router_ip)

    run_analysis()


def get_speeds():
    st = speedtest.Speedtest()
    st.download()
    st.upload()
    download_result = round(st.results.download / 1e6, 2)  # Rounded to 2 decimal places
    upload_result = round(st.results.upload / 1e6, 2)  # Rounded to 2 decimal places
    print(f"Speedtest result: {download_result} Mbps / {upload_result} Mbps")

    print_table_ping_line(
        get_current_datetime_string("%H:%M:%S"),
        "Speedtest (DL)",
        download_result,
        " ",
        1,
        " ",
        " ",
    )

    print_table_ping_line(
        get_current_datetime_string("%H:%M:%S"),
        "Speedtest (UL)",
        upload_result,
        " ",
        1,
        " ",
        " ",
    )

    return download_result, upload_result


def run_analysis():
    summarized_ping = 0
    number_of_pings = 0
    failed_pings = 0

    summarized_dns_resolve_time = 0
    number_of_dns_resolves = 0
    failed_dns_resolves = 0

    summarized_download_speed = 0
    summarized_upload_speed = 0
    number_of_speedtests = 0

    def add_speedtest_values(download_speed, upload_speed):
        nonlocal summarized_download_speed, summarized_upload_speed, number_of_speedtests
        summarized_download_speed += download_speed
        summarized_upload_speed += upload_speed
        number_of_speedtests += 1

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

    # router_ip = os.getenv("ROUTER_IP")
    router_ip = get_router_ip()
    test_runs = config["test_rounds"]
    print_tests = os.getenv("PRINT_TESTS")
    completed_test_runs = 0

    if print_tests:
        print_table_headers(
            "Timestamp", "Type", "Result (ms)", "Target", "Succeeded", "SNR", "Channel"
        )
    for _ in range(test_runs):
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

                avg_download_speed = summarized_download_speed / completed_test_runs
                avg_upload_speed = summarized_upload_speed / completed_test_runs
                print(f"Average download speed: {avg_download_speed:.2f} Mbps")
                print(f"Average upload speed: {avg_upload_speed:.2f} Mbps")
                print(f"Speedtests: {number_of_speedtests}")
            else:
                print("No tests were completed.")
            break

        # PINGS
        ping_router = ping("ping router", router_ip)
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
            download_speed, upload_speed = get_speeds()
            summarized_download_speed += download_speed
            summarized_upload_speed += upload_speed

        pause_interval = int(os.getenv("PAUSE_INTERVAL_LENGTH"), 0)
        time.sleep(pause_interval)
