class AnalysisData:
    def __init__(self):
        self.pings = []
        self.failed_pings = []
        self.dns_resolves = []
        self.failed_dns_resolves = []
        self.speedtest = []

    # Appenders
    def add_ping(self, item):
        self.pings.append(item)

    def add_dns_resolve(self, item):
        self.dns_resolves.append(item)

    def add_speedtest(self, item):
        self.speedtest.append(item)
