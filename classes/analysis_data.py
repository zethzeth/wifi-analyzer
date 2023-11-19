from tabulate import tabulate

from config import config
from helpers.date_helpers import get_prettified_datetime_from_unix
from helpers.print_helpers import print_block_title
from helpers.report_helpers import calculate_stats


class AnalysisData:
    def __init__(self):
        self.pings = []
        self.failed_pings = 0
        self.dns_resolves = []
        self.failed_dns_resolves = 0
        self.download_speedtests = []
        self.failed_download_speedtests = 0
        self.upload_speedtests = []
        self.failed_upload_speedtests = 0
        self.router_snr = []
        self.router_signals = []
        self.router_noises = []
        self.router_channels = []

    # Appenders
    def add_ping(self, item):
        if (item == -1):
            self.failed_pings += 1
        else:
            self.pings.append(item)

    def add_dns_resolve(self, item):
        if item == -1:
            self.failed_dns_resolves += 1
        else:
            self.dns_resolves.append(item)

    def add_download_speedtest(self, item):
        if item == -1:
            self.failed_download_speedtests += 1
        else:
            self.download_speedtests.append(item)

    def add_upload_speedtest(self, item):
        if item == -1:
            self.failed_upload_speedtests += 1
        else:
            self.upload_speedtests.append(item)

    def add_signal_and_noise(self, signal, noise):
        snr = signal - noise
        self.router_signals.append(signal)
        self.router_noises.append(noise)
        self.router_snr.append(snr)

    def add_channel(self, channel):
        # Extracting the first numeric part of the string
        numeric_part = channel.split(' ')[0]  # Splits the string at spaces and takes the first part
        try:
            numeric_value = int(numeric_part)  # Converts the extracted part to an integer
            self.router_channels.append(numeric_value)
        except ValueError:
            print(f"Invalid channel format: {channel}")

    def print_report(self):
        self.print_meta_report()
        self.print_overall_report()
        self.print_router_report()

    def print_meta_report(self):
        print_block_title("Meta info")
        start_time = get_prettified_datetime_from_unix(config['test_start_unix_stamp'])
        end_time = get_prettified_datetime_from_unix(config['test_end_unix_stamp'])
        print("Start: " + start_time)
        print("End: " + end_time)

    def print_overall_report(self):

        print_block_title('Overall result')
        table_data = []

        # Download speedtests
        if self.download_speedtests:
            total_downloads, avg_download, median_download = calculate_stats(self.download_speedtests)

            download_success_ratio = 'N/A'
            download_speedtests_count = len(self.download_speedtests)
            if (download_speedtests_count > 0):
                failed_download_ratio = self.failed_download_speedtests / download_speedtests_count;
                download_success_ratio = (download_speedtests_count - failed_download_ratio) / download_speedtests_count
                download_success_ratio = download_success_ratio * 100

            # Adding to table data
            table_data.append(
                ["Download", len(self.download_speedtests), f"{avg_download:.0f} mbps", f"{median_download:.0f} mbps",
                 f"{download_success_ratio:.2f}%"])
        else:
            table_data.append(["Download", 0, "0 mbps", "0 mbps", "0.00%"])

        # Upload speedtests
        if self.upload_speedtests:
            total_uploads, avg_upload, median_upload = calculate_stats(self.upload_speedtests)

            # Upload ratio
            upload_success_ratio = 'N/A'
            upload_speedtests_count = len(self.upload_speedtests)
            if (upload_speedtests_count > 0):
                failed_upload_ratio = self.failed_upload_speedtests / upload_speedtests_count;
                upload_success_ratio = (upload_speedtests_count - failed_upload_ratio) / upload_speedtests_count
                upload_success_ratio = upload_success_ratio * 100

            table_data.append(
                ["Upload", len(self.upload_speedtests), f"{avg_upload:.0f} mbps", f"{median_upload:.0f} mbps",
                 f"{upload_success_ratio:.2f}%"])
        else:
            table_data.append(["Upload", 0, "0 mbps", "0 mbps", "0.00%"])

        # For Pings
        successful_pings = [item[0] for item in self.pings if item[0] != -1]
        total_pings, avg_ping, median_ping = calculate_stats(successful_pings)
        success_ratio_ping = len(successful_pings) / len(self.pings) * 100 if self.pings else 0
        table_data.append(
            ["Ping", len(self.pings), f"{avg_ping:.0f} ms", f"{median_ping:.0f} ms", f"{success_ratio_ping:.2f}%"])

        # For DNS Resolves
        successful_dns = [item[0] for item in self.dns_resolves if item[0] != -1]
        total_dns, avg_dns, median_dns = calculate_stats(successful_dns)
        success_ratio_dns = len(successful_dns) / len(self.dns_resolves) * 100 if self.dns_resolves else 0
        table_data.append(
            ["DNS", len(self.dns_resolves), f"{avg_dns:.0f} ms", f"{median_dns:.0f} ms", f"{success_ratio_dns:.2f}%"])

        headers = ["Type", "   #", "    Avg", "Median", "Success-ratio"]
        column_alignments = ('right',) * len(headers)
        print(tabulate(table_data, headers, tablefmt="simple", colalign=column_alignments))

    def print_router_report(self):
        table_data = []
        total_snr, avg_snr, median_snr = calculate_stats(self.router_snr)
        min_snr = min(self.router_snr)
        max_snr = max(self.router_snr)

        total_signal, avg_signal, median_signal = calculate_stats(self.router_signals)
        min_signal = min(self.router_signals)
        max_signal = max(self.router_signals)

        total_noise, avg_noise, median_noise = calculate_stats(self.router_noises)
        min_noise = min(self.router_noises)
        max_noise = max(self.router_noises)

        total_channel, avg_channel, median_channel = calculate_stats(self.router_channels)
        min_channel = min(self.router_channels)
        max_channel = max(self.router_channels)

        table_data.append(["SNR", len(self.router_snr), f"{avg_snr:.0f}", f"{median_snr:.0f}", f"{min_snr:.0f}",
                           f"{max_snr:.0f}"])
        table_data.append(
            ["Signal", len(self.router_signals), f"{avg_signal:.0f}", f"{median_signal:.0f}", f"{min_signal:.0f}",
             f"{max_signal:.0f}"])
        table_data.append(
            ["Noise", len(self.router_noises), f"{avg_noise:.0f}", f"{median_noise:.0f}", f"{min_noise:.0f}",
             f"{max_noise:.0f}"])
        table_data.append(
            ["Channel", len(self.router_channels), f"{avg_channel:.0f}", f"{median_channel:.0f}",
             f"{min_channel:.0f}",
             f"{max_channel:.0f}"])

        print_block_title('Router result')
        headers = ["Type", "  #", "  Avg", "Median", "Min", "Max"]
        column_alignments = ('right',) * len(headers)
        print(tabulate(table_data, headers, tablefmt="simple", colalign=column_alignments))
