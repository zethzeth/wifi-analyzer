import select
import sys
import threading
import time
from pprint import pprint

import services.router_service as router_service
import services.speedtest_service as speedtest_service
from config import config
from helpers.date_helpers import get_current_datetime_string, get_prettified_datetime_from_unix
from helpers.print_helpers import (
    print_block_title, print_table_cell, print_table_header_line, print_table_header,
)
from services.dns_service import resolve_domain
from services.network_service import ping


def display_info():
    print_block_title("Router info")
    router_ip = router_service.get_router_ip()
    router_details = router_service.get_router_details()
    pprint(router_details)
    print("IP: " + router_ip)

    print_block_title("Other routers")
    router_service.print_details_of_all_routers()

    print_block_title('Test details')
    for key, value in config.items():
        if (key == 'test_start_unix_stamp' or key == 'test_end_unix_stamp'):
            human_readable_date = get_prettified_datetime_from_unix(value, "%Y-%m-%d--%H-%M-%S")
            print(f"{key}: {value} ({human_readable_date})")
        else:
            print(f"{key}: {value}")
    print(f"\n\n")


def run_pings_and_dns(analysis_data, run_event):
    while run_event.is_set():
        # PINGS
        router_ip = router_service.get_router_ip()
        router_details = router_service.get_router_details()

        if (config['connection_type'] == 'wifi'):
            sig, noise, ch = router_service.get_signal_noise_and_channel(router_details)
            analysis_data.add_signal_and_noise(sig, noise)
            analysis_data.add_channel(ch)
        else:
            sig = 0
            noise = 0
            ch = 0

        target = router_ip
        target_name = "router"
        type = "ping " + target_name
        response_time, succeeded = ping(target)
        print_ping_or_dns_line(type, target, response_time, succeeded, sig, noise, ch)
        analysis_data.add_ping([response_time, target_name])

        target = "8.8.8.8"
        target_name = "google"
        type = "ping " + target_name
        response_time, succeeded = ping(target)
        print_ping_or_dns_line(type, target, response_time, succeeded, sig, noise, ch)
        analysis_data.add_ping([response_time, target_name])

        target = "dr.dk"
        target_name = "dr"
        type = "ping " + target_name
        response_time, succeeded = ping(target)
        print_ping_or_dns_line(type, target, response_time, succeeded, sig, noise, ch)
        analysis_data.add_ping([response_time, target_name])

        # DNS
        target = "google.com"
        target_name = "google"
        type = "dig " + target_name
        response_time, succeeded = resolve_domain(target)
        print_ping_or_dns_line(type, target, response_time, succeeded, sig, noise, ch)
        analysis_data.add_dns_resolve([response_time, target_name])

        target = "dr.dk"
        target_name = "dr"
        type = "dig " + target_name
        response_time, succeeded = resolve_domain(target)
        print_ping_or_dns_line(type, target, response_time, succeeded, sig, noise, ch)
        analysis_data.add_dns_resolve([response_time, target_name])

        time.sleep(1)  # 1 second break


def run_speedtests(analysis_data, run_event):
    while run_event.is_set():
        if config["run_speedtests"]:
            download_speed, upload_speed = speedtest_service.get_speeds()
            analysis_data.add_download_speedtest(download_speed)
            analysis_data.add_upload_speedtest(upload_speed)

        time.sleep(1)  # 1 second break


def run_analysis():
    analysis_data = config['analysis_data']

    col_widths = config['ping_and_dns_table_widths']
    print_table_header_line(col_widths)
    col = 0
    print_table_header("Timestamp", col_widths[col])
    col += 1
    print_table_header("Type", col_widths[col])
    col += 1
    print_table_header("Target", col_widths[col])
    col += 1
    print_table_header("Result (ms)", col_widths[col])
    col += 1
    print_table_header("Succeeded", col_widths[col])
    col += 1
    print_table_header("SNR", col_widths[col])
    col += 1
    print_table_header("Channel", col_widths[col], is_last=True)
    print_table_header_line(col_widths)

    # Event to signal the threads to stop
    run_event = threading.Event()
    run_event.set()

    # Starting threads
    ping_dns_thread = threading.Thread(target=run_pings_and_dns, args=(analysis_data, run_event))
    speedtest_thread = threading.Thread(target=run_speedtests, args=(analysis_data, run_event))

    ping_dns_thread.start()
    speedtest_thread.start()

    try:
        end_unix_stamp = config['test_end_unix_stamp']
        while time.time() < end_unix_stamp:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:  # If Enter is hit
                break
            time.sleep(config['pause_between_tests'])

    finally:
        # Stop the threads
        run_event.clear()
        ping_dns_thread.join()
        speedtest_thread.join()

        # Print report after threads have stopped
        analysis_data.print_report()


def print_ping_or_dns_line(type, target, result, succeeded, signal, noise, channel):
    snr_str = router_service.get_snr_string(signal, noise)
    timestamp = get_current_datetime_string("%H:%M:%S")
    col_widths = config['ping_and_dns_table_widths']

    # if not target:
    col = 0
    print_table_cell(timestamp, col_widths[col])

    col += 1
    print_table_cell(type, col_widths[col])

    col += 1
    print_table_cell(target, col_widths[col])

    col += 1
    result_color = 'white'
    try:
        result_int_value = int(result)
        if result_int_value > 300:
            result_color = 'red'
        elif result_int_value > 150:
            result_color = 'yellow'
    except ValueError:
        pass
    print_table_cell(result, col_widths[col], result_color)

    col += 1
    succeeded_color = 'white'
    if not succeeded:
        succeeded_color = 'red'
    print_table_cell(succeeded, col_widths[col], succeeded_color)

    col += 1
    print_table_cell(snr_str, col_widths[col])

    col += 1
    print_table_cell(channel, col_widths[col], is_last=True)

    return
