import os
import time
from helpers.concurrent_helpers import run_concurrently
from helpers.test_helpers import function_one, function_two
from helpers.print_helpers import (
    print_formatted,
    print_block_title,
    print_table_headers,
)

from database.db import get_connection
from core.analysis_state import AnalysisState

from services.network_service import ping
from services.dns_service import resolve_domain


def start_new_analysis():
    conn = get_connection()
    cursor = conn.cursor()

    # Insert into the 'analyses' table
    cursor.execute(
        """
        INSERT INTO analyses (name, location, domain)
        VALUES (?, ?, ?)
        """,
        (os.getenv("ANALYSIS_NAME"), os.getenv("LOCATION"), os.getenv("TEST_DOMAIN")),
    )
    state = AnalysisState()
    state.analysis_id = cursor.lastrowid
    print_formatted("Analysis_id:", state.analysis_id)
    conn.commit()
    conn.close()

    print_block_title("Starting analysis")

    run_analysis()


def run_analysis():
    # results = run_concurrently(function_one, function_two)
    router_ip = os.getenv("ROUTER_IP")
    test_runs = int(os.getenv("TEST_RUNS"), 0)
    print_tests = os.getenv("PRINT_TESTS")
    if print_tests:
        print_table_headers("Timestamp", "Type", "Result (ms)", "Target", "Succeeded")
    for _ in range(test_runs):
        ping("ping router", router_ip)
        ping("ping google", "8.8.8.8")
        ping("ping dr", "dr.dk")
        resolve_domain()
        pause_interval = int(os.getenv("PAUSE_INTERVAL_LENGTH"), 0)
        time.sleep(pause_interval)
