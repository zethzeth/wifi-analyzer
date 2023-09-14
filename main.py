import os
from dotenv import load_dotenv
from colorama import init, Fore, Style
from helpers.setup_helpers import setup_db
from helpers.date_helpers import get_current_datetime_string

# Initialize colorama
init(autoreset=True)

# Load the .env file
load_dotenv()


def get_user_input():
    print(f"{Fore.MAGENTA}Welcome to the Connection Tester!\n")

    # ---

    print(f"---\n{Fore.BLUE}## Meta settings")

    # Get test name input
    print("Test name:")
    test_name = input()
    if not test_name:
        test_name = get_current_datetime_string()

    # ---

    print(f"---\n{Fore.BLUE}## Remote settings")

    #  Domain
    print("Domain (Defaults to: google.com):")
    domain = input()
    if not domain.strip():  # If the input is blank, set it to default
        domain = "google.com"

    # ---

    print(f"---\n{Fore.BLUE}## Local settings\n")

    #  Location
    print("Location:")
    location = input()
    if not location.strip():
        location = "Unknown"

    return location, domain, test_name


if __name__ == "__main__":
    setup_db()

    # Get variables
    location, domain, test_name = get_user_input()
    print(f"\nLocation: {location}")
    print(f"Domain: {domain}")
    print(f"Test Name: {test_name}")
