# Kestrel

A Wi-Fi and connection analyzer for debugging a bad connection at a specific desk. It pings the router, the ISP's first hop and several internet hosts, times DNS, runs speedtests, tracks the signal and which access point you're on, maps how crowded each Wi-Fi channel is, and ends with a plain-language diagnosis.

Runs on Linux and macOS. One Python engine does the measuring; you drive it from the desktop app or the terminal.

## Setup

Needs Python 3.10+, `ping` and `dig` (`bind9-dnsutils` on Debian/Ubuntu). On Linux also `iw`, `nmcli` and `resolvectl`. The desktop app needs Node.js.

```
make ship        # Desktop app (sets up the Python venv and npm deps on first run)
make run         # The same test in the terminal
make channels    # Channel-load scan in the terminal
make test        # Parser and analysis tests
```

Every run is logged to `kestrel.db` (SQLite): the measurements and each signal/access-point reading. `make reset-db` deletes it.

### macOS

- Live signal readings use Apple's CoreWLAN (installed automatically on macOS), and channel scans use `system_profiler`.
- macOS hides network names and access-point MACs from apps without Location Services. Grant it to your terminal (System Settings → Privacy & Security → Location Services) to see them. Without it, roam detection can't tell access points apart.

### Linux: the Electron sandbox

Ubuntu 24.04+ blocks the unprivileged user namespaces Electron's sandbox needs, so `make ship` passes `--no-sandbox` on Linux. The app only loads its own local files, but to keep the sandbox, allow Electron in AppArmor (run from the repo root) and drop the flag from the Makefile:

```bash
sudo tee /etc/apparmor.d/kestrel-electron <<EOF
abi <abi/4.0>,
include <tunables/global>
profile kestrel-electron $(pwd)/app/node_modules/electron/dist/electron flags=(unconfined) {
  userns,
}
EOF
sudo apparmor_parser -r /etc/apparmor.d/kestrel-electron
```

## Debugging a desk

1. **Run at the problem desk** for 15+ minutes, sitting where the person sits. Set *Location* so the runs can be told apart later.
2. **Run somewhere the Wi-Fi is known to be good**, and compare.
3. **Read the diagnosis.** The router ping separates "Wi-Fi at this desk" from "internet/ISP". Signal, SNR, roams and the channel map explain *why* the Wi-Fi is bad.
4. **Remember it's your adapter.** If your laptop is fine at the desk and theirs isn't, suspect their machine: driver, power-saving, a USB-C dock, or a 2.4 GHz-only adapter.

What the diagnosis looks for:

- **Router ping loss or jitter**: the local link is unstable.
- **Internet bad, router fine**: the problem is upstream. Kestrel pings the router, the ISP's first hop (the first public address on the route to 8.8.8.8, found with `tracepath`/`traceroute` when a test starts), and then Google, Cloudflare and dr.dk. The first segment that goes bad is the culprit: office router/firewall vs. the ISP's network vs. a single service.
- **Signal below −67/−75 dBm, low SNR, low link rate**: too far from an access point, or interference.
- **Roaming back and forth**: two access points are equally weak at the desk.
- **A stronger access point for the same network in range**: the client is "sticky" and won't roam.
- **2.4 GHz while 5 GHz is available**: band steering is off.
- **A crowded channel**: neighbouring radios on or overlapping your channel.
- **Bufferbloat**: latency balloons while a speedtest fills the link. Speedtests start after 20 s of idle baseline and repeat every minute; pings taken during them are kept as separate "under load" series.

## Channel load

The Channels tab (or `make channels`) scans for nearby access points and scores each 20 MHz channel. **Load** is the signal-weighted count of other radios overlapping it: a neighbour at −45 dBm or louder counts 1, one at −70 counts 0.5, one at −95 counts 0. 2.4 GHz overlap is partial (channels are 5 MHz apart); 5/6 GHz networks wider than 20 MHz occupy their whole 40/80/160 MHz block. Access points broadcasting several SSIDs from one radio count once. It's a proxy for contention, not measured airtime. Scanning briefly takes the radio off-channel, so the app won't scan during a test.

## Windows (no install)

`windows/kestrel.bat` is a standalone version of the same test for locked-down Windows machines: no Python, no admin, no install. Double-click it, answer the questions, and it saves a `kestrel-*.txt` report next to itself (or in `%TEMP%`) with the raw `netsh`/`ipconfig` output and recent Wi-Fi disconnect events appended.

- Signal is converted from Windows' 0-100% and is approximate; there's no noise/SNR, and channel widths are unknown.
- Windows 11 24H2 hides Wi-Fi details until Location is on; the script opens that setting.
- The speedtest uses Cloudflare (`speed.cloudflare.com`) instead of Ookla.

## Layout

- `kestrel/runner.py`: one analysis; link, probe and speedtest threads that emit events
- `kestrel/cli.py` / `kestrel/bridge.py`: the terminal front end / the JSON-lines bridge the app talks to
- `kestrel/platforms/`: gateway, DNS server, Wi-Fi link and scans for `linux.py` and `macos.py`
- `kestrel/probes.py`: ping, DNS (`dig` straight to the upstream resolver) and speedtest
- `kestrel/channels.py`, `kestrel/diagnosis.py`, `kestrel/results.py`: channel load, findings, statistics
- `app/`: the Electron app; `main.js` spawns `python -m kestrel serve`
- `windows/kestrel.bat`: the standalone Windows version

## Speedtest

It uses Ookla's `speedtest-cli` library, where it'll attempt a download of a large file (like speedtest.net).

## Useful commands

```
#  Trace the dig
dig +trace google.com
```

...Is it resolving the IP in the router? 


```
# Wi-Fi info
iw dev wlan0 link                   # Linux
system_profiler SPAirPortDataType   # macOS

# Ping and traceroute
ping 8.8.8.8
traceroute 8.8.8.8
```

## Applications and tools

A list of applications I use.

### iAnalyzeWifi

Price: 59 DKK
Not worth premium. Don't buy.
Platform: Mac


### LanScan

Good for finding devices on network.
Not worth premium. Don't buy.
Platform: Mac

### Ultra Wifi

Gives a good analysis. Plus signal history! 
Premium is worth it, I'd say. But get the lifetime option.
Platform: Mac

### iWifi

Seems good. 
Seems worth Premium. 
Untried
Platform: Mac

### MTR

Platform: Mac or Linux
Has to run with sudo, like: `sudo mtr 8.8.8.8`

Free and pretty interesting.


