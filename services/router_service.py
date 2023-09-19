import os
import subprocess
import ipaddress
from dotenv import load_dotenv
from helpers.print_helpers import (
    print_color,
    print_block_title,
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
    raise ValueError("No valid IP address found")


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
