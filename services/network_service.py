import re
import subprocess

from helpers.date_helpers import get_current_datetime_string
from helpers.print_helpers import (
    print_table_ping_line,
)
from services.router_service import get_router_details


def ping(event_type, ip_to_ping):
    succeeded = 1

    router_details = get_router_details()
    # pprint(router_details)
    #     {'802.11 auth': 'open',
    #  'BSSID': '',
    #  'MCS': '15',
    #  'NSS': '2',
    #  'SSID': 'Zeth’s iPhone',
    #  'agrCtlNoise': '-71',
    #  'agrCtlRSSI': '-41',
    #  'agrExtNoise': '0',
    #  'agrExtRSSI': '0',
    #  'channel': '6',
    #  'guardInterval': '800',
    #  'lastAssocStatus': '0',
    #  'lastTxRate': '130',
    #  'link auth': 'wpa2-psk',
    #  'maxRate': '144',
    #  'op mode': 'station',
    #  'state': 'running'}

    router_signal = router_details.get("agrCtlRSSI")
    if router_signal is not None:
        router_signal = int(router_signal)

    router_noise = router_details.get("agrCtlNoise")
    if router_noise is not None:
        router_noise = int(router_noise)

    router_snr = "N/A"
    if isinstance(router_signal, int) and isinstance(router_noise, int):
        router_snr = router_signal - router_noise

    router_channel = router_details.get("channel")

    router_snr_string = (
            str(router_snr) + " (" + str(router_signal) + ", " + str(router_noise) + ")"
    )
    exception = None

    try:
        ping_count = 1
        output = subprocess.check_output(
            f"ping -c {ping_count} {ip_to_ping}",
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        # Extract ping time from output
        match = re.search("time=(\d+\.\d+) ms", output)
        if match:
            response_time = int(match.group(1).split(".")[0])
            # db.add_log_to_db(event_type, response_time, ip_to_ping, succeeded)
    except subprocess.CalledProcessError as e:
        succeeded = 0
        response_time = 0
        # db.add_log_to_db(event_type, None, ip_to_ping, succeeded)
        exception = e

    print_table_ping_line(
        get_current_datetime_string("%H:%M:%S"),
        event_type,
        response_time,
        ip_to_ping,
        succeeded,
        router_snr_string,
        router_channel,
    )
    if not succeeded:
        print("Command execution failed!")
        print(f"Command: {exception.cmd}")
        print(f"Return code: {exception.returncode}")
        print("Output/Error:")
        print(exception.output)  # or print(e.stdout)
    return response_time
