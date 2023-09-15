import concurrent.futures


def run_concurrently(*functions):
    """
    Run the provided functions concurrently using ThreadPoolExecutor.

    Args:
        *functions (callable): Functions to be executed concurrently.

    Returns:
        List: The results of each function after execution.
    """
    results = []
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Using list comprehension to initiate concurrent tasks
            futures = [executor.submit(function) for function in functions]

            # Wait for all tasks to complete and gather the results
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

    except KeyboardInterrupt:
        # Handling KeyboardInterrupt, can add custom cleanup logic here if needed
        print("Keyboard interrupt detected. Stopping threads...")
        for future in futures:
            future.cancel()

    return results
