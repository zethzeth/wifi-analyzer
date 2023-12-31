import os

import speedtest


def get_speeds():
    try:
        st = speedtest.Speedtest()
        st.download()
        st.upload()
        download_result = round(
            st.results.download / 1e6, 2
        )  # Rounded to 2 decimal places
        upload_result = round(st.results.upload / 1e6, 2)  # Rounded to 2 decimal places
    except speedtest.SpeedtestBestServerFailure:
        if int(os.getenv('DEBUG_VERBOSITY')) > 3:
            print("Error: Unable to connect to servers to test latency.")
        download_result = -1
        upload_result = -1
    except Exception as e:
        if int(os.getenv('DEBUG_VERBOSITY')) > 3:
            print(f"An error occurred during the speed test: {e}")
        download_result = -1
        upload_result = -1

    print(f"Speedtest result: {download_result} Mbps / {upload_result} Mbps")
    return [download_result, upload_result]
