import os
from dotenv import load_dotenv
from services.meta_service import print_env_variables
from database.db import setup_db
from services.analysis_service import start_new_analysis
from helpers.print_helpers import print_block_title
from config import config

load_dotenv()


def prompt_for_settings():
    # Prompt for running speedtests
    run_speedtests = input("Run speedtests? (y/n): ").strip().lower() != "n"
    config["run_speedtests"] = run_speedtests

    # Prompt for the number of test rounds
    test_rounds_input = input("Amount of test-rounds to do: ").strip()
    try:
        test_rounds = int(test_rounds_input)
    except ValueError:
        test_rounds = 99999

    print("Test rounds: " + str(test_rounds))
    config["test_rounds"] = test_rounds


if __name__ == "__main__":
    print_block_title("Welcome to the Connection Tester!", "MAGENTA")
    setup_db()

    prompt_for_settings()

    print_env_variables()

    start_new_analysis()
