# Turns a finished test into plain-language findings, worst first.
# Thresholds follow common enterprise Wi-Fi guidance (e.g. -67 dBm for voice/video, SNR 25 dB).

OK, WARN, BAD = 'ok', 'warn', 'bad'


def diagnose(summary: dict, channel_report: dict | None, connection: dict) -> list[dict]:
    findings = []
    add = lambda level, title, detail: findings.append({'level': level, 'title': title, 'detail': detail})
    net = summary['network']
    link = summary['link']
    wireless = connection['link']['wireless']

    router = net.get('ping router')
    isp = net.get('ping isp')
    idle = {name: s for name, s in net.items() if not name.endswith(' under load')}
    internet = {name: s for name, s in idle.items() if name.startswith('ping ') and name not in ('ping router', 'ping isp')}
    dns = [s for name, s in idle.items() if name.startswith('dns ')]

    # Local link: router ping isolates Wi-Fi (or the cable) from the ISP
    if router and router['attempts']:
        if router['loss'] > 0.02 or (router['avg'] or 0) > 30 or (router['jitter'] or 0) > 20:
            add(BAD, 'The link to the router is unstable',
                f'Router ping: {_pct(router["loss"])} loss, {_ms(router["avg"])} avg, {_ms(router["jitter"])} jitter. '
                'A healthy local link is ~0% loss and under 10 ms. The problem is between this desk and the access point.')
        elif router['loss'] > 0 or (router['avg'] or 0) > 10:
            add(WARN, 'The link to the router has occasional hiccups',
                f'Router ping: {_pct(router["loss"])} loss, {_ms(router["avg"])} avg, {_ms(router["jitter"])} jitter.')
        else:
            add(OK, 'The link to the router is solid', f'{_ms(router["avg"])} avg, no loss.')
    elif not connection['router_ip']:
        add(WARN, 'No router to ping', 'Could not find the default gateway.')

    # Internet: walk outwards (router → ISP hop → destinations) and blame the first segment that goes bad.
    # Loss on the ISP hop alone proves nothing: ISP routers rate-limit pings aimed at themselves.
    bad = {name[5:]: s for name, s in internet.items() if _is_bad(s, loss=0.02, avg=100)}
    if bad:
        local_ok = router and not _is_bad(router, loss=0, avg=10)
        isp_bad = isp and _is_bad(isp, loss=0.02, avg=50)
        worst = f'Worst: {_pct(max(s["loss"] or 0 for s in bad.values()))} loss, {_ms(max(s["avg"] or 0 for s in bad.values()))} avg.'
        if len(bad) < len(internet):
            add(WARN, f'Only {", ".join(bad)} is lossy or slow',
                f'{worst} The other destinations are fine, so it is that service, not this connection.')
        elif not local_ok:
            add(WARN, 'Internet traffic is lossy or slow', f'{worst} Fix the local link first; it is likely the cause.')
        elif isp_bad:
            add(BAD, 'Traffic is lost between the office router and the ISP',
                f'{worst} The router is fine but the ISP\'s first hop already suffers: the office router/firewall or the ISP line.')
        elif isp:
            add(BAD, 'Traffic is lost beyond the ISP\'s first hop',
                f'{worst} Everything up to the ISP is fine, so the problem is further out in the ISP\'s network.')
        else:
            add(BAD, 'Internet traffic is lossy or slow beyond the router',
                f'{worst} The local link is fine, so look at the router/firewall/ISP.')

    # DNS: slow lookups make "the internet is slow" even when pings are fine
    if dns:
        dns_avg = max(s['avg'] or 0 for s in dns)
        dns_loss = max(s['loss'] or 0 for s in dns)
        if dns_loss > 0.02 or dns_avg > 100:
            add(WARN, 'DNS lookups are slow or failing', f'{_pct(dns_loss)} failed, {_ms(dns_avg)} avg.')

    # Bufferbloat: latency that balloons while a speedtest fills the link makes calls stutter during uploads/downloads
    bloat = [(name, net[f'{name} under load']['avg'] - s['avg']) for name, s in idle.items()
             if name.startswith('ping ') and s['avg'] is not None and (net.get(f'{name} under load') or {}).get('avg')]
    worst = max(bloat, key=lambda b: b[1], default=None)
    if worst and worst[1] > 100:
        add(WARN, 'Latency balloons under load (bufferbloat)',
            f'{worst[0]} is {worst[1]:.0f} ms slower while a speedtest runs. Video calls will stutter when someone uploads/downloads.')

    if not wireless:
        return _sorted(findings)

    signal = link.get('signal')
    if signal:
        if signal['avg'] < -75:
            add(BAD, 'Weak signal', f'Avg {signal["avg"]:.0f} dBm (worst {signal["min"]:.0f}). '
                'Below -75 dBm expect retries and slow rates. The desk is too far from an access point, or something blocks it.')
        elif signal['avg'] < -67:
            add(WARN, 'Signal is marginal', f'Avg {signal["avg"]:.0f} dBm. Aim for -67 dBm or better for calls/video.')
        else:
            add(OK, 'Signal strength is good', f'Avg {signal["avg"]:.0f} dBm.')
        if signal['max'] - signal['min'] > 15:
            add(WARN, 'Signal swings a lot', f'From {signal["min"]:.0f} to {signal["max"]:.0f} dBm. '
                'People moving, doors, or the adapter switching antennas/access points.')

    snr = link.get('snr')
    if snr and snr['avg'] < 25:
        add(BAD if snr['avg'] < 15 else WARN, 'Low signal-to-noise ratio',
            f'Avg SNR {snr["avg"]:.0f} dB. Interference is drowning the signal (microwaves, monitors, docks, other networks).')

    rate = link.get('tx_rate')
    if rate and rate['avg'] < 50:
        add(WARN, 'Low link rate', f'The adapter negotiates ~{rate["avg"]:.0f} Mbit/s; typically from weak signal or 2.4 GHz.')

    if summary['roams'] >= 3:
        add(BAD, 'Roaming back and forth between access points',
            f'{summary["roams"]} roams across {len(summary["access_points"])} access points. '
            'Each roam can drop calls. Two APs are probably equally weak at this desk.')
    elif summary['roams']:
        add(WARN, 'Roamed between access points', f'{summary["roams"]} roam(s) during the test.')

    if summary['drops']:
        add(BAD, 'The Wi-Fi connection dropped', f'{summary["drops"]} reading(s) with no association.')

    if channel_report:
        findings += _channel_findings(channel_report, connection['link'])

    return _sorted(findings)


def _channel_findings(report: dict, link: dict) -> list[dict]:
    findings = []
    current = next((c for c in report['bands'].get(link.get('band'), []) if c['current']), None)
    best = next((c for c in report['bands'].get(link.get('band'), []) if c['recommended']), None)
    if current and current['load'] >= 2:
        findings.append({'level': WARN, 'title': f'Channel {current["channel"]} is crowded',
                         'detail': f'{current["radios"]} other radios overlap it (load {current["load"]:.1f}).'
                         + (f' Channel {best["channel"]} looks quieter (load {best["load"]:.1f}).' if best else '')})

    # A stronger AP for the same network nearby means the client is "sticky" or roaming is misconfigured
    same = [n for n in report['networks'] if n['ssid'] and n['ssid'] == link.get('ssid') and n['bssid'] != link.get('bssid')]
    stronger = [n for n in same if link.get('signal') is not None and n['signal'] >= link['signal'] + 8]
    if stronger:
        best_ap = max(stronger, key=lambda n: n['signal'])
        findings.append({'level': WARN, 'title': 'A stronger access point is in range',
                         'detail': f'Connected at {link["signal"]} dBm, but {best_ap["bssid"] or "another AP"} '
                         f'({best_ap["band"]}, ch {best_ap["channel"]}) is at {best_ap["signal"]} dBm. '
                         'The client is not roaming to it.'})

    if link.get('band') == '2.4 GHz' and any(n['band'] != '2.4 GHz' and n['signal'] > -70 for n in same):
        findings.append({'level': WARN, 'title': 'Connected on 2.4 GHz although 5 GHz is available',
                         'detail': '2.4 GHz is slower and more crowded. Band steering may be off.'})
    return findings


def _is_bad(series: dict, loss: float, avg: float) -> bool:
    return (series['loss'] or 0) > loss or (series['avg'] or 0) > avg


def _sorted(findings: list[dict]) -> list[dict]:
    order = {BAD: 0, WARN: 1, OK: 2}
    return sorted(findings, key=lambda f: order[f['level']])


def _pct(value: float | None) -> str:
    return f'{value:.1%}' if value is not None else 'N/A'


def _ms(value: float | None) -> str:
    return f'{value:.0f} ms' if value is not None else 'N/A'
