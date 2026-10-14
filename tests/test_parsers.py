# Parsers run against captured command output, so both platforms are covered from either OS.
import unittest

from kestrel import channels, probes
from kestrel.diagnosis import diagnose
from kestrel.models import Link, Network
from kestrel.platforms import linux, macos
from kestrel.results import Results

IW_LINK = """Connected to a8:53:7d:20:47:82 (on wlp0s20f3)
\tSSID: BN-IoT
\tfreq: 5640.0
\tsignal: -39 dBm
\trx bitrate: 286.7 MBit/s HE-MCS 11 HE-NSS 2
\ttx bitrate: 286.7 MBit/s HE-MCS 11 HE-NSS 2
"""
IW_INFO = """Interface wlp0s20f3
\tssid BN-IoT
\ttype managed
\tchannel 128 (5640 MHz), width: 20 MHz, center1: 5640 MHz
"""
IW_SCAN_DUMP = """BSS a8:53:7d:20:47:82(on wlp0s20f3) -- associated
\tfreq: 5640.0
\tsignal: -39.00 dBm
\tSSID: BN-IoT
BSS 7c:77:16:05:84:35(on wlp0s20f3)
\tfreq: 2437.0
\tsignal: -25.00 dBm
\tSSID: 3Bredband-8435
\t\tBSSID: 7c:77:16:05:84:99
"""
NMCLI = """*:BN-IoT:A8\\:53\\:7D\\:20\\:47\\:82:128:5640 MHz:20 MHz:100
 :3Bredband-8435:7C\\:77\\:16\\:05\\:84\\:35:6:2437 MHz:20 MHz:100
 ::7E\\:77\\:16\\:85\\:84\\:35:104:5520 MHz:80 MHz:60
"""


class LinuxParsers(unittest.TestCase):
    def test_link(self):
        link = linux.parse_link('wlp0s20f3', IW_LINK, IW_INFO)
        self.assertEqual((link.ssid, link.bssid, link.signal), ('BN-IoT', 'a8:53:7d:20:47:82', -39))
        self.assertEqual((link.channel, link.width, link.band, link.tx_rate), (128, 20, '5 GHz', 286.7))

    def test_scan_signals_ignore_nested_bssids(self):
        self.assertEqual(linux.parse_scan_signals(IW_SCAN_DUMP), {'a8:53:7d:20:47:82': -39, '7c:77:16:05:84:35': -25})

    def test_nmcli_networks(self):
        found = linux.parse_nmcli_networks(NMCLI, {'7c:77:16:05:84:35': -25})
        self.assertEqual([n.ssid for n in found], ['BN-IoT', '3Bredband-8435', None])
        self.assertTrue(found[0].in_use)
        self.assertEqual(found[1].signal, -25)  # Real dBm from iw wins
        self.assertEqual(found[2].signal, -70)  # Score 60 → rough dBm
        self.assertEqual((found[2].band, found[2].width), ('5 GHz', 80))


class MacParsers(unittest.TestCase):
    def test_modern_profiler_entry(self):
        network = macos.parse_profiler_network({
            '_name': 'Office', 'spairport_network_channel': '36 (5GHz, 80MHz)', 'spairport_signal_noise': '-55 dBm / -92 dBm',
        })
        self.assertEqual((network.ssid, network.channel, network.band, network.width, network.signal),
                         ('Office', 36, '5 GHz', 80, -55))

    def test_legacy_profiler_entry(self):
        network = macos.parse_profiler_network({'_name': 'Old', 'spairport_network_channel': 6,
                                                'spairport_signal_noise': '-70 dBm / -95 dBm'})
        self.assertEqual((network.channel, network.band, network.width), (6, '2.4 GHz', 20))

    def test_6ghz_profiler_entry(self):
        network = macos.parse_profiler_network({'spairport_network_channel': '37 (6GHz, 160MHz)',
                                                'spairport_signal_noise': '-60 dBm / -96 dBm'})
        self.assertEqual((network.band, network.width), ('6 GHz', 160))

    def test_unparseable_entry(self):
        self.assertIsNone(macos.parse_profiler_network({'_name': 'x'}))


def net(channel, band='2.4 GHz', width=20, signal=-45, bssid=None, ssid='x', in_use=False):
    return Network(ssid, bssid, channel, band, width, signal, in_use)


class ChannelLoad(unittest.TestCase):
    def test_24ghz_overlap(self):
        self.assertEqual(channels.overlap(net(6), 6), 1)
        self.assertEqual(channels.overlap(net(6), 8), 0.5)
        self.assertEqual(channels.overlap(net(1), 6), 0)  # 1/6/11 don't overlap

    def test_5ghz_blocks(self):
        self.assertEqual(channels.occupied_channels(net(44, '5 GHz', 80)), [36, 40, 44, 48])
        self.assertEqual(channels.occupied_channels(net(157, '5 GHz', 80)), [149, 153, 157, 161])
        self.assertEqual(channels.occupied_channels(net(112, '5 GHz', 160)), [100 + 4 * i for i in range(8)])

    def test_multi_ssid_radio_counts_once(self):
        nets = [net(11, bssid=f'd4:20:b0:e8:7e:4{i}', ssid=f'ssid{i}') for i in range(4)]
        report = channels.analyse(nets)
        ch11 = next(c for c in report['bands']['2.4 GHz'] if c['channel'] == 11)
        self.assertEqual((ch11['radios'], ch11['load']), (1, 1.0))

    def test_own_radio_excluded_and_quietest_marked(self):
        link = Link('wlan0', True, bssid='aa:aa:aa:aa:aa:01', channel=6, band='2.4 GHz', signal=-40)
        report = channels.analyse([net(6, bssid='aa:aa:aa:aa:aa:01', in_use=True), net(1, bssid='bb:bb:bb:bb:bb:01'),
                                   net(11, bssid='cc:cc:cc:cc:cc:01')], link)
        band = {c['channel']: c for c in report['bands']['2.4 GHz']}
        self.assertEqual(band[6]['load'], 0)
        self.assertTrue(band[6]['current'] and band[6]['recommended'])


class Roaming(unittest.TestCase):
    def test_roams_counted(self):
        results = Results()
        for bssid in ['a', 'a', 'b', 'a']:
            results.add_link(Link('wlan0', True, bssid=bssid, signal=-60))
        self.assertEqual((results.roams, results.summary()['access_points']), (2, ['a', 'b']))


TRACEPATH = """ 1?: [LOCALHOST]                      pmtu 1500
 1:  10.45.33.129                                          1.307ms
 1:  10.45.33.129                                          1.072ms
 2:  169.254.45.13                                         2.141ms
 3:  194.50.40.3                                           2.902ms
 4:  no reply
"""
TRACEROUTE = """traceroute to 8.8.8.8 (8.8.8.8), 10 hops max, 52 byte packets
 1  192.168.1.1  2.1 ms
 2  * 
 3  100.64.0.1  5.0 ms
 4  80.62.1.1  9.3 ms
"""


class Hops(unittest.TestCase):
    def test_tracepath(self):
        self.assertEqual(probes.parse_hops(TRACEPATH), ['10.45.33.129', '169.254.45.13', '194.50.40.3'])

    def test_traceroute(self):
        self.assertEqual(probes.parse_hops(TRACEROUTE), ['192.168.1.1', '100.64.0.1', '80.62.1.1'])


def summary_with(**pings):
    results = Results()
    for name, (ms, lost) in pings.items():
        for i in range(50):
            results.add(f'ping {name}', None if i < lost else ms, 'ms')
    return results.summary()


class Diagnosis(unittest.TestCase):
    connection = {'router_ip': '10.0.0.1', 'link': {'wireless': False}}

    def titles(self, **pings):
        return [f['title'] for f in diagnose(summary_with(**pings), None, self.connection)]

    def test_blames_isp_segment(self):
        titles = self.titles(router=(2, 0), isp=(80, 5), google=(90, 5), cloudflare=(90, 5))
        self.assertIn('Traffic is lost between the office router and the ISP', titles)

    def test_blames_beyond_isp(self):
        titles = self.titles(router=(2, 0), isp=(5, 0), google=(90, 5), cloudflare=(90, 5))
        self.assertIn("Traffic is lost beyond the ISP's first hop", titles)

    def test_single_destination(self):
        titles = self.titles(router=(2, 0), google=(10, 10), cloudflare=(10, 0))
        self.assertIn('Only google is lossy or slow', titles)

    def test_flags_weak_signal_and_flapping(self):
        results = Results()
        for i in range(10):
            results.add('ping router', 3, 'ms')
            results.add_link(Link('wlan0', True, bssid='ab'[i % 2], signal=-80))
        connection = {'router_ip': '10.0.0.1', 'link': {'wireless': True}}
        titles = [f['title'] for f in diagnose(results.summary(), None, connection) if f['level'] == 'bad']
        self.assertIn('Weak signal', titles)
        self.assertIn('Roaming back and forth between access points', titles)


if __name__ == '__main__':
    unittest.main()
