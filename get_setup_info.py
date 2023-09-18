import os
import subprocess
from pprint import pprint
from dotenv import load_dotenv
from helpers.print_helpers import (
    print_color,
    print_block_title,
    print_table_line,
    print_table_header,
)
from services.router_service import get_router_ip, get_router_details

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
        else:
            print(f"Couldn't determine the first nameserver for {domain}.")

    except subprocess.CalledProcessError:
        print_color("Error executing dig command.", "red")


if __name__ == "__main__":
    # get_first_nameserver()
    router_details = get_router_details()
    print_color("Router Details")
    pprint(router_details)
    print()

    router_ip = get_router_ip()
    print_color("Router IP")
    print(router_ip)
