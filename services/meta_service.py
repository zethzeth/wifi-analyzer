import os
from helpers.print_helpers import print_formatted, print_color


def print_env_variables():
    print_color("# Settings")

    # Define a list of environment variables and their corresponding display names
    env_vars = [
        ("ANALYSIS_NAME", "Test name"),
        ("TEST_DOMAIN", "Domain"),
        ("LOCATION", "Location"),
        ("PAUSE_INTERVAL_LENGTH", "Pause interval length"),
        ("PING_COUNT", "Ping count"),
        ("TEST_RUNS", "Test runs"),
        ("PRINT_TESTS", "Print tests"),
        ("EXPLAIN_FAILED_PINGS", "Explain failed pings"),
    ]

    # Iterate over each environment variable and its display name
    for env_var, display_name in env_vars:
        value = os.getenv(env_var)
        if not value:
            print_color(f"{env_var} environment variable is not set.", "red")
            raise EnvironmentError(f"{env_var} environment variable is not set.")
        print_formatted(display_name, value)
