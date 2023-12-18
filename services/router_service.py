import ipaddress
import subprocess

from dotenv import load_dotenv

from config import config
from helpers.print_helpers import (
    print_color,
)

load_dotenv()


def get_router_ip():
    # Get the default gateway (often the router's IP in home setups)
    router_ip = None
    try:
        full_router_info = subprocess.check_output(
            "netstat -nr | grep default",
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        for line in full_router_info.split("\n"):
            parts = line.split()
            if (
                    len(parts) > 1 and "." in parts[1]
            ):  # Check for '.' to quickly identify a potential IPv4 address
                ip_candidate = parts[1]
                try:
                    # Check if the candidate is a valid IPv4 address
                    ipaddress.IPv4Address(ip_candidate)
                    return ip_candidate
                except ipaddress.AddressValueError:
                    pass  # Not a valid IPv4 address, so continue to the next line

    except subprocess.CalledProcessError:
        print("Error getting the router's IP.")

    # If the function has not returned by now, it means no valid IP was found
    # raise ValueError("No valid IP address found")
    return ''


# pprint(get_router_details)
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
def get_router_details():
    router_details = {}

    try:
        raw_output = subprocess.check_output(
            [
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-I",
            ],
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Parse the output into a dictionary
        for line in raw_output.strip().split("\n"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                router_details[key] = value

    except subprocess.CalledProcessError:
        print_color("Error getting WiFi details or not connected to WiFi.", "red")

    return router_details


def print_details_of_all_routers():
    try:
        raw_output = subprocess.check_output(
            [
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-s",
            ],
            stderr=subprocess.STDOUT,
            text=True,
        )
        print(raw_output)
    except subprocess.CalledProcessError:
        print_color("Error getting details of other WiFi details.", "red")


def get_signal_noise_and_channel(router_details):
    if router_details == "{'AirPort': 'Off'}":
        return 0, 0, 0

    if (config['connection_type'] == 'cabled'):
        return 0, 0, 0

    signal = router_details.get("agrCtlRSSI")
    if signal is not None:
        signal = int(signal)

    noise = router_details.get("agrCtlNoise")
    if noise is not None:
        noise = int(noise)

    # channel = router_details.get("channel")
    channel = get_channel(router_details)

    return signal, noise, channel


def get_channel(router_details):
    channel = router_details.get("channel")
    if isinstance(channel, (str, list)):
        if ',' in channel:
            primary, width = channel.split(',')
            return f"{primary} ({width})"
        else:
            return channel


def get_snr_string(signal, noise):
    snr = "N/A"
    if isinstance(signal, int) and isinstance(noise, int):
        snr = signal - noise
        return str(snr) + " (" + str(signal) + ", " + str(noise) + ")"
    else:
        return "N/A"
