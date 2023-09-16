import os
import subprocess
from dotenv import load_dotenv
from helpers.print_helpers import (
    print_color,
    print_block_title,
    print_table_line,
    print_table_header,
    print_table_footer,
)

load_dotenv()


def get_first_nameserver():
    domain = os.getenv("TEST_DOMAIN")
    print_block_title("First nameserver", "blue")

    nameserver = None
    try:
        # Execute the dig command
        result = subprocess.check_output(
            ["dig", "+trace", domain], stderr=subprocess.STDOUT, text=True
        )

        # Parse the output to find the first nameserver
        for line in result.split("\n"):
            if "Received " in line:
                parts = line.split()
                if len(parts) > 4:
                    nameserver = parts[
                        5
                    ]  # Return the IP address of the first nameserver
                    # return parts[5].split("#")[0]

        if nameserver:
            print_table_header("Domain", "Nameserver", col_widths=[30, 50])
            print_table_line(domain, nameserver, col_widths=[30, 50])
            print_table_footer(col_widths=[30, 50])
        else:
            print(f"Couldn't determine the first nameserver for {domain}.")

    except subprocess.CalledProcessError:
        print_color("Error executing dig command.", "red")


def get_router_details():
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
            ):  # Check for '.' to confirm it's an IPv4 address
                router_ip = parts[1]
                break
    except subprocess.CalledProcessError:
        print_color("Error getting the router's IP.", "red")

    # Get some details about the WiFi connection (if you're connected via WiFi)
    try:
        wifi_details = subprocess.check_output(
            [
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-I",
            ],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError:
        wifi_details = "Error getting WiFi details or not connected to WiFi."

    print_block_title("WiFi details", "blue")
    print(wifi_details)

    print_block_title("Router info", "blue")
    if router_ip:
        print(router_ip)
    else:
        print(full_router_info)


if __name__ == "__main__":
    get_first_nameserver()
    get_router_details()
