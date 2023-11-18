from tabulate import tabulate

from helpers.print_helpers import print_block_title
from helpers.report_helpers import calculate_stats


class AnalysisData:
    def __init__(self):
        self.pings = []
        self.failed_pings = []
        self.dns_resolves = []
        self.failed_dns_resolves = []
        self.speedtests = []

    # Appenders
    def add_ping(self, item):
        if (item == -1):
            self.failed_pings.append(item)
        else:
            self.pings.append(item)

    def add_dns_resolve(self, item):
        self.dns_resolves.append(item)

    def add_speedtest(self, item):
        self.speedtests.append(item)

    def print_report(self):
        self.print_overall_report()

    def print_overall_report(self):

        print_block_title('Result')
        table_data = []

        # For Speedtests
        if self.speedtests:
            download_speeds = [item[0] for item in self.speedtests]
            upload_speeds = [item[1] for item in self.speedtests]

            # Calculating stats for download speeds
            total_downloads, avg_download, median_download = calculate_stats(download_speeds)
            # Assuming all speed tests are successful, as there's no indication of failure in the data
            success_ratio_download = 100

            # Calculating stats for upload speeds
            total_uploads, avg_upload, median_upload = calculate_stats(upload_speeds)
            # Assuming all speed tests are successful
            success_ratio_upload = 100

            # Adding to table data
            table_data.append(
                ["Download", len(self.speedtests), f"{avg_download:.0f} mbps", f"{median_download:.0f} mbps",
                 f"{success_ratio_download:.2f}%"])
            table_data.append(
                ["Upload", len(self.speedtests), f"{avg_upload:.0f} mbps", f"{median_upload:.0f} mbps",
                 f"{success_ratio_upload:.2f}%"])
        else:
            table_data.append(["Download", 0, "0 mbps", "0 mbps", "0.00%"])
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

        headers = ["Type", "   #", "    Avg (ms)", "Median (ms)", "Success-ratio"]
        column_alignments = ('right',) * len(headers)
        print(tabulate(table_data, headers, tablefmt="simple", colalign=column_alignments))
