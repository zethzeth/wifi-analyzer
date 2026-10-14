<# : Batch launcher - cmd runs these lines, PowerShell skips them as a comment and runs the rest of the file
@echo off
set "KESTREL_SCRIPT=%~f0"
set "KESTREL_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -LiteralPath $env:KESTREL_SCRIPT -Raw | Invoke-Expression"
echo.
pause
exit /b
#>

# Kestrel for Windows: the `make run` Wi-Fi test using only what ships with Windows (netsh, ping, Resolve-DnsName).
# No install and no admin. Loaded via iex, so execution policy doesn't apply, and it sticks to cmdlets so
# Constrained Language Mode on locked-down machines still works. The report is saved as a .txt to send back.
$ProgressPreference = 'SilentlyContinue'  # The progress bar makes Invoke-WebRequest ~10x slower in PowerShell 5

$InternetTargets = [ordered]@{ google = '8.8.8.8'; cloudflare = '1.1.1.1'; dr = 'dr.dk' }  # Router and ISP hop are added at runtime
$DnsTargets = [ordered]@{ google = 'google.com'; dr = 'dr.dk' }
$FullLanguage = $ExecutionContext.SessionState.LanguageMode -eq 'FullLanguage'
$State = @{ series = [ordered]@{}; bssids = @(); roams = 0; drops = 0; bands = @(); link = $null; raw = [ordered]@{} }

#region Output

function Say([string]$text = '', $color) {
    if ($color) { Write-Host $text -ForegroundColor $color } else { Write-Host $text }
    Add-Content -LiteralPath $ReportPath -Value $text -Encoding UTF8
}

function Title([string]$text, $color = 'Cyan') { Say ''; Say "## $text" $color }

function Fit([string]$text, [int]$width) {
    if ($text.Length -ge $width) { $text = $text.Substring(0, $width - 4) + '...' }
    $text.PadRight($width)
}

function Num($value, $unit) { if ($null -eq $value) { '-' } else { '{0:0} {1}' -f $value, $unit } }

function Pct($value) { if ($null -eq $value) { 'N/A' } else { '{0:0.0}%' -f ($value * 100) } }

function Report-Path([string]$name) {
    # Matches characters that aren't safe in a file name.
    # ✔ "Anna's desk" -> Anna_s_desk  ✔ "a/b" -> a_b  ✘ "desk-2" stays
    $file = 'kestrel-{0}-{1:yyyy-MM-dd--HH-mm-ss}.txt' -f ($name -replace '[^\w-]', '_'), (Get-Date)
    foreach ($dir in @($env:KESTREL_DIR, $env:TEMP)) {
        if (-not $dir) { continue }
        $path = Join-Path $dir $file
        try { Set-Content -LiteralPath $path -Value '' -ErrorAction Stop; return $path } catch {}
    }
}

#endregion

#region Platform

function Get-Connection {
    # Lowest-metric default route; VPN on-link routes (next hop 0.0.0.0) aren't a router to ping
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Where-Object { $_.NextHop -ne '0.0.0.0' } |
        Sort-Object { $_.RouteMetric + $_.InterfaceMetric } | Select-Object -First 1
    if (-not $route) { return @{ router = $null; adapter = $null; dns = $null; wireless = $false } }

    $adapter = Get-NetAdapter -InterfaceIndex $route.ifIndex -ErrorAction SilentlyContinue
    $dns = (Get-DnsClientServerAddress -InterfaceIndex $route.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses |
        Select-Object -First 1
    @{
        router   = $route.NextHop
        adapter  = $adapter
        dns      = $dns
        wireless = [bool]($adapter -and ($adapter.PhysicalMediaType -match '802\.11' -or $adapter.NdisPhysicalMedium -eq 9))
    }
}

# netsh labels are translated (Danish "Kanal" etc.), so fields are found by the shape of their value where possible
function Parse-Pairs([string]$text) {
    foreach ($line in $text -split "`r?`n") {
        # Matches a "Label : value" line, splitting on the first colon only.
        # ✔ "    AP BSSID   : a8:53:7d:20:47:82"  ✔ "    Signal : 80%"  ✘ "There is 1 interface on the system:"
        if ($line -match '^\s+([^:]+?)\s*:\s?(.*)$') { [pscustomobject]@{ Key = $Matches[1]; Value = $Matches[2].Trim() } }
    }
}

function Find-Value($pairs, [string]$keyPattern, [string]$valuePattern = '.') {
    ($pairs | Where-Object { $_.Key -match $keyPattern -and $_.Value -match $valuePattern } | Select-Object -First 1).Value
}

function Band-For($channel) {
    if (-not $channel) { $null } elseif ($channel -le 14) { '2.4 GHz' } else { '5 GHz' }  # 6 GHz can't be told apart by channel
}

function Get-Link($adapterName) {
    $raw = (netsh wlan show interfaces) -join "`n"
    $State.raw['netsh wlan show interfaces'] = $raw
    $blocks = $raw -split "`n\s*`n"
    $block = $blocks | Where-Object { (Parse-Pairs $_ | Select-Object -First 1).Value -eq $adapterName } | Select-Object -First 1
    $pairs = @(Parse-Pairs $block)
    $ssid = Find-Value $pairs '^SSID$'
    if (-not $ssid) { return @{ wireless = $false } }

    $percent = Find-Value $pairs '.' '^\d+\s?%$'  # ✔ 80%  ✔ 80 %  ✘ 802.11ax
    $channel = Find-Value $pairs 'Channel|Kanal|Canal|Kanaal' '^\d+$'
    $rates = @($pairs | Where-Object { $_.Key -match '\(Mbps\)' } | ForEach-Object { $_.Value })  # Receive, then transmit
    $band = Find-Value $pairs '.' '^[\d.]+ GHz$'  # ✔ 5 GHz  ✔ 2.4 GHz  ✘ 802.11ac
    @{
        wireless = $true
        ssid     = $ssid
        bssid    = Find-Value $pairs 'BSSID' '^([0-9a-f]{2}:){5}[0-9a-f]{2}$'  # ✔ a8:53:7d:20:47:82  ✘ A8-53-7D-20-47-82  ✘ 00:11
        signal   = if ($percent) { [int]($percent -replace '\D') / 2 - 100 } else { $null }  # Windows maps -100..-50 dBm onto 0..100%
        percent  = $percent
        channel  = if ($channel) { [int]$channel } else { $null }
        band     = if ($band) { $band } else { Band-For ([int]$channel) }
        radio    = Find-Value $pairs '.' '^802\.11'
        rx_rate  = if ($rates.Count -ge 1) { [double]$rates[0] } else { $null }
        tx_rate  = if ($rates.Count -ge 2) { [double]$rates[1] } else { $null }
    }
}

function Get-Networks {
    $raw = netsh wlan show networks mode=bssid
    $State.raw['netsh wlan show networks mode=bssid'] = $raw -join "`n"
    $found = @()
    $ssid = $null
    $current = $null
    foreach ($line in $raw) {
        # Matches a network header; the SSID may be empty for hidden networks.
        # ✔ "SSID 1 : Home"  ✔ "SSID 2 : "  ✘ "    BSSID 1 : a8:53:..."
        if ($line -match '^SSID \d+ : ?(.*)$') { $ssid = $Matches[1].Trim(); continue }
        # Matches one access point under the current network.
        # ✔ "    BSSID 1                 : a8:53:7d:20:47:82"  ✘ "SSID 1 : Home"  ✘ "    BSSID 1 : "
        if ($line -match '^\s+BSSID \d+\s*: ([0-9a-f:]{17})') {
            if ($current) { $found += $current }
            $current = @{ ssid = $ssid; bssid = $Matches[1]; signal = $null; channel = $null; band = $null }
            continue
        }
        if (-not $current) { continue }
        if ($line -match ':\s*(\d+)\s?%\s*$') { $current.signal = [int]$Matches[1] / 2 - 100 }  # ✔ "Signal : 80%"  ✔ "Signal : 80 %"  ✘ "Channel Utilization : 32 (12 %)"
        elseif ($line -match '(Channel|Kanal|Canal|Kanaal)\s*:\s*(\d+)\s*$') { $current.channel = [int]$Matches[2] }  # ✔ "Channel : 36"  ✘ "Channel Utilization : 32 (12 %)"
        elseif ($line -match ':\s*([\d.]+ GHz)\s*$') { $current.band = $Matches[1] }  # ✔ "Band : 5 GHz"  ✘ "Radio type : 802.11ax"
    }
    if ($current) { $found += $current }

    foreach ($net in $found) {
        if (-not $net.band) { $net.band = Band-For $net.channel }
        $net.in_use = $State.link -and $net.bssid -eq $State.link.bssid
    }
    @($found | Where-Object { $_.channel -and $null -ne $_.signal })
}

function Assert-LocationAccess {
    # Windows 11 24H2 hides SSIDs and scans from netsh until Location is on, and says so with this settings link
    if (((netsh wlan show interfaces) -join ' ') -notmatch 'ms-settings:privacy-location') { return }
    Say 'Windows hides Wi-Fi details until Location is turned on.' Yellow
    Say 'In the window that opens: turn on "Location services" and "Let desktop apps access your location".' Yellow
    try { Start-Process 'ms-settings:privacy-location' } catch {}
    Read-Host 'Press Enter when done (or just Enter to continue without Wi-Fi details)' | Out-Null
}

#endregion

#region Probes

function Ping-Host($target) {
    if (-not $target) { return $null }
    if ($FullLanguage) {
        try {
            $reply = (New-Object System.Net.NetworkInformation.Ping).Send($target, 2000)
            if ($reply.Status -eq 'Success') { return [double]$reply.RoundtripTime }
        } catch {}
        return $null
    }
    $reply = Test-Connection -ComputerName $target -Count 1 -ErrorAction SilentlyContinue  # Slower, but allowed in Constrained Language Mode
    if ($reply) { [double]$reply.ResponseTime } else { $null }
}

# First public hop that answers ping: usually the ISP's edge router, just past the office router/firewall
function Find-IspHop($target = '8.8.8.8') {
    $output = tracert -d -h 10 -w 1000 $target
    $State.raw['tracert -d -h 10 -w 1000 8.8.8.8'] = $output -join "`n"
    $hops = foreach ($line in $output) {
        # Matches a hop line ending in the hop's IPv4 address.
        # ✔ "  2     1 ms    <1 ms     1 ms  10.0.0.1"  ✘ "  3     *     *     *     Request timed out."  ✘ "Tracing route to 8.8.8.8 over a maximum of 10 hops"
        if ($line -match '^\s*\d+\s.*?(\d+\.\d+\.\d+\.\d+)\s*$') { $Matches[1] }
    }
    $public = @($hops | Select-Object -Unique | Where-Object { $_ -ne $target -and (Test-PublicIp $_) })
    foreach ($ip in $public | Select-Object -First 3) { if ($null -ne (Ping-Host $ip)) { return $ip } }
    $null
}

# Not private, loopback, link-local, multicast or carrier-grade NAT (100.64/10)
function Test-PublicIp([string]$ip) {
    $o = [int[]]($ip -split '\.')
    -not ($o[0] -in 0, 10, 127 -or $o[0] -ge 224 -or ($o[0] -eq 169 -and $o[1] -eq 254) -or ($o[0] -eq 192 -and $o[1] -eq 168) -or
        ($o[0] -eq 172 -and $o[1] -ge 16 -and $o[1] -le 31) -or ($o[0] -eq 100 -and $o[1] -ge 64 -and $o[1] -le 127))
}

function Resolve-Timed($domain, $server) {
    $query = @{ Name = $domain; Type = 'A'; DnsOnly = $true; NoHostsFile = $true; QuickTimeout = $true; ErrorAction = 'Stop' }
    if ($server) { $query.Server = $server }  # Ask the resolver directly, so the local DNS cache doesn't answer
    try { (Measure-Command { Resolve-DnsName @query | Out-Null }).TotalMilliseconds } catch { $null }
}

# Runs as a background job so pings keep going during it: latency under load shows bufferbloat
$SpeedtestJob = {
    $ProgressPreference = 'SilentlyContinue'
    try { [Net.ServicePointManager]::SecurityProtocol = 'Tls12' } catch {}
    $result = @{ download = $null; upload = $null }
    try {
        $bytes = 25000000
        $seconds = (Measure-Command { Invoke-WebRequest "https://speed.cloudflare.com/__down?bytes=$bytes" -UseBasicParsing -TimeoutSec 90 -ErrorAction Stop | Out-Null }).TotalSeconds
        $result.download = $bytes * 8 / $seconds / 1000000
    } catch {}
    try {
        $body = '0' * 10000000
        $seconds = (Measure-Command { Invoke-WebRequest 'https://speed.cloudflare.com/__up' -Method Post -Body $body -UseBasicParsing -TimeoutSec 90 -ErrorAction Stop | Out-Null }).TotalSeconds
        $result.upload = $body.Length * 8 / $seconds / 1000000
    } catch {}
    $result
}

#endregion

#region Results

function Add-Sample([string]$name, $value, [string]$unit) {
    if (-not $State.series.Contains($name)) { $State.series[$name] = @{ unit = $unit; values = @(); failures = 0 } }
    if ($null -eq $value) { $State.series[$name].failures++ } else { $State.series[$name].values += [double]$value }
}

# Records a link reading; returns the previous BSSID when this reading is a roam
function Add-Link($link) {
    if (-not $link.wireless -or $null -eq $link.signal) { $State.drops++; return $null }
    foreach ($name in 'signal', 'tx_rate', 'rx_rate') {
        if ($null -ne $link[$name]) { Add-Sample "wifi $name" $link[$name] $(if ($name -eq 'signal') { 'dBm' } else { 'Mbit/s' }) }
    }
    if ($link.band -and $State.bands -notcontains $link.band) { $State.bands += $link.band }
    if (-not $link.bssid -or ($State.bssids.Count -and $State.bssids[-1] -eq $link.bssid)) { return $null }
    $previous = if ($State.bssids.Count) { $State.bssids[-1] } else { $null }
    $State.bssids += $link.bssid
    if ($previous) { $State.roams++ }
    $previous
}

function Get-Stats($series) {
    $values = @($series.values)
    $count = $values.Count
    $attempts = $count + $series.failures
    $stats = @{ unit = $series.unit; attempts = $attempts; avg = $null; median = $null; min = $null; max = $null; jitter = $null; loss = $null }
    if ($attempts) { $stats.loss = $series.failures / $attempts }
    if (-not $count) { return $stats }

    $measure = $values | Measure-Object -Average -Minimum -Maximum
    $sorted = @($values | Sort-Object)
    $stats.avg = $measure.Average
    $stats.min = $measure.Minimum
    $stats.max = $measure.Maximum
    $stats.median = if ($count % 2) { $sorted[($count - 1) / 2] } else { ($sorted[$count / 2 - 1] + $sorted[$count / 2]) / 2 }
    if ($count -ge 2) {
        # Mean change between consecutive samples, as in RFC 3550
        $total = 0
        for ($i = 1; $i -lt $count; $i++) { $d = $values[$i] - $values[$i - 1]; if ($d -lt 0) { $d = -$d }; $total += $d }
        $stats.jitter = $total / ($count - 1)
    }
    $stats
}

#endregion

#region Channels

$ChannelPlan = [ordered]@{
    '2.4 GHz' = 1..13
    '5 GHz'   = @(36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165)
    '6 GHz'   = @(for ($c = 1; $c -le 233; $c += 4) { $c })
}

# netsh doesn't report channel widths, so every network counts as 20 MHz here
function Get-ChannelLoad($networks, $link) {
    # One radio broadcasting several SSIDs shows up as BSSIDs differing only in the last octet; count it once
    $radio = { '{0} {1}' -f $_.bssid.Substring(0, 14), $_.channel }
    $ours = @($networks | Where-Object in_use | ForEach-Object $radio)  # The radio we're on isn't competition
    $others = @($networks | Where-Object { (& $radio) -notin $ours } | Group-Object $radio |
        ForEach-Object { $_.Group | Sort-Object signal -Descending | Select-Object -First 1 })
    $bands = [ordered]@{}
    foreach ($band in $ChannelPlan.Keys) {
        $inBand = @($others | Where-Object { $_.band -eq $band })
        if ($band -eq '6 GHz' -and -not $inBand.Count) { continue }
        $loads = foreach ($channel in $ChannelPlan[$band]) {
            $load = 0; $count = 0; $strongest = $null
            foreach ($net in $inBand) {
                $distance = $net.channel - $channel; if ($distance -lt 0) { $distance = -$distance }
                $share = if ($band -eq '2.4 GHz') { (4 - $distance) / 4 } elseif ($distance -eq 0) { 1 } else { 0 }  # 2.4 GHz spills +-2 channels
                $weight = ($net.signal + 95) / 50  # -45 dBm and up -> 1, -70 -> 0.5, -95 -> 0
                if ($weight -gt 1) { $weight = 1 }
                if ($share -le 0 -or $weight -le 0) { continue }
                $load += $weight * $share; $count++
                if ($null -eq $strongest -or $net.signal -gt $strongest) { $strongest = $net.signal }
            }
            [pscustomobject]@{ channel = $channel; load = $load; networks = $count; strongest = $strongest
                current = [bool]($link.band -eq $band -and $link.channel -eq $channel); recommended = $false }
        }
        if ($band -eq '6 GHz') { $loads = @($loads | Where-Object { $_.networks }) }

        # Only 1/6/11 don't overlap on 2.4 GHz; DFS channels on 5 GHz can be forced off by radar
        $candidates = @($loads | Where-Object { $band -ne '2.4 GHz' -or $_.channel -in 1, 6, 11 })
        if ($band -eq '5 GHz') { $nonDfs = @($candidates | Where-Object { $_.channel -lt 52 -or $_.channel -gt 144 }); if ($nonDfs.Count) { $candidates = $nonDfs } }
        $best = $candidates | Sort-Object load, channel | Select-Object -First 1
        if ($best) { $best.recommended = $true }
        $bands[$band] = @($loads)
    }
    $bands
}

function Show-Channels($bands, $networks) {
    foreach ($band in $bands.Keys) {
        Title "Channel load - $band"
        $peak = ($bands[$band] | Measure-Object load -Maximum).Maximum
        if ($peak -lt 1) { $peak = 1 }
        foreach ($l in $bands[$band]) {
            $bar = '#' * [int]($l.load / $peak * 40)
            $tags = $(if ($l.current) { ' <- you' }) + $(if ($l.recommended) { ' * quietest' })
            Say ('{0,4}  {1,-40} {2,5:0.0}  {3,2} nets{4}' -f $l.channel, $bar, $l.load, $l.networks, $tags) $(if ($l.current) { 'Magenta' })
        }
    }
    Title 'Nearby access points'
    $table = $networks | Sort-Object signal -Descending | ForEach-Object {
        [pscustomobject]@{ SSID = $(if ($_.ssid) { $_.ssid } else { '(hidden)' }); BSSID = $_.bssid; Band = $_.band
            Ch = $_.channel; Signal = "$($_.signal) dBm"; Use = $(if ($_.in_use) { '*' } else { '' }) }
    } | Format-Table -AutoSize | Out-String
    Say $table.TrimEnd()
    Say 'Load = signal-weighted count of overlapping networks (all counted as 20 MHz wide).'
}

#endregion

#region Diagnosis

# Same thresholds as kestrel/diagnosis.py; there's no noise floor on Windows, so no SNR finding
function Get-Findings($net, $wifi, $channelLoad, $networks, $link) {
    $findings = @()
    $add = { param($level, $title, $detail) $findings += [pscustomobject]@{ level = $level; title = $title; detail = $detail } }
    $idle = @($net.Keys | Where-Object { $_ -notlike '* under load' })
    $router = $net['ping router']
    $isp = $net['ping isp']
    $internet = @($idle | Where-Object { $_ -like 'ping *' -and $_ -notin 'ping router', 'ping isp' })
    $dns = @($idle | Where-Object { $_ -like 'dns *' } | ForEach-Object { $net[$_] })

    if ($router -and $router.attempts) {
        $detail = "Router ping: $(Pct $router.loss) loss, $(Num $router.avg 'ms') avg, $(Num $router.jitter 'ms') jitter."
        if ($router.loss -gt 0.02 -or $router.avg -gt 30 -or $router.jitter -gt 20) {
            . $add bad 'The link to the router is unstable' "$detail A healthy local link is ~0% loss and under 10 ms. The problem is between this desk and the access point."
        } elseif ($router.loss -gt 0 -or $router.avg -gt 10) {
            . $add warn 'The link to the router has occasional hiccups' $detail
        } else {
            . $add ok 'The link to the router is solid' "$(Num $router.avg 'ms') avg, no loss."
        }
    } else {
        . $add warn 'No router to ping' 'Could not find the default gateway.'
    }

    # Walk outwards (router -> ISP hop -> destinations) and blame the first segment that goes bad.
    # Loss on the ISP hop alone proves nothing: ISP routers rate-limit pings aimed at themselves.
    $bad = @($internet | Where-Object { $net[$_].loss -gt 0.02 -or $net[$_].avg -gt 100 })
    if ($bad.Count) {
        $badStats = @($bad | ForEach-Object { $net[$_] })
        $worst = "Worst: $(Pct ($badStats | Measure-Object loss -Maximum).Maximum) loss, $(Num ($badStats | Measure-Object avg -Maximum).Maximum 'ms') avg."
        $localOk = $router -and $router.loss -eq 0 -and $router.avg -le 10
        $ispBad = $isp -and ($isp.loss -gt 0.02 -or $isp.avg -gt 50)
        if ($bad.Count -lt $internet.Count) {
            . $add warn "Only $(($bad | ForEach-Object { $_.Substring(5) }) -join ', ') is lossy or slow" "$worst The other destinations are fine, so it is that service, not this connection."
        } elseif (-not $localOk) {
            . $add warn 'Internet traffic is lossy or slow' "$worst Fix the local link first; it is likely the cause."
        } elseif ($ispBad) {
            . $add bad 'Traffic is lost between the office router and the ISP' "$worst The router is fine but the ISP's first hop already suffers: the office router/firewall or the ISP line."
        } elseif ($isp) {
            . $add bad "Traffic is lost beyond the ISP's first hop" "$worst Everything up to the ISP is fine, so the problem is further out in the ISP's network."
        } else {
            . $add bad 'Internet traffic is lossy or slow beyond the router' "$worst The local link is fine, so look at the router/firewall/ISP."
        }
    }

    if ($dns.Count) {
        $loss = ($dns | Measure-Object loss -Maximum).Maximum
        $avg = ($dns | Measure-Object avg -Maximum).Maximum
        if ($loss -gt 0.02 -or $avg -gt 100) { . $add warn 'DNS lookups are slow or failing' "$(Pct $loss) failed, $(Num $avg 'ms') avg." }
    }

    # Latency that balloons while a speedtest fills the link makes calls stutter during uploads/downloads
    $worst = $idle | Where-Object { $_ -like 'ping *' -and $null -ne $net[$_].avg -and $net["$_ under load"].avg } |
        ForEach-Object { [pscustomobject]@{ name = $_; extra = $net["$_ under load"].avg - $net[$_].avg } } |
        Sort-Object extra -Descending | Select-Object -First 1
    if ($worst -and $worst.extra -gt 100) {
        . $add warn 'Latency balloons under load (bufferbloat)' ("{0} is {1:0} ms slower while a speedtest runs. Video calls will stutter when someone uploads/downloads." -f $worst.name, $worst.extra)
    }

    $signal = $wifi['wifi signal']
    if ($signal -and $signal.avg) {
        if ($signal.avg -lt -75) {
            . $add bad 'Weak signal' ("Avg {0:0} dBm (worst {1:0}). Below -75 dBm expect retries and slow rates. The desk is too far from an access point, or something blocks it." -f $signal.avg, $signal.min)
        } elseif ($signal.avg -lt -67) {
            . $add warn 'Signal is marginal' ("Avg {0:0} dBm. Aim for -67 dBm or better for calls/video." -f $signal.avg)
        } else {
            . $add ok 'Signal strength is good' ("Avg {0:0} dBm." -f $signal.avg)
        }
        if ($signal.max - $signal.min -gt 15) {
            . $add warn 'Signal swings a lot' ("From {0:0} to {1:0} dBm. People moving, doors, or the adapter switching antennas/access points." -f $signal.min, $signal.max)
        }
    }

    $rate = $wifi['wifi tx_rate']
    if ($rate -and $rate.avg -lt 50) { . $add warn 'Low link rate' ("The adapter negotiates ~{0:0} Mbit/s; typically from weak signal or 2.4 GHz." -f $rate.avg) }

    if ($State.roams -ge 3) {
        . $add bad 'Roaming back and forth between access points' "$($State.roams) roams across $(@($State.bssids | Select-Object -Unique).Count) access points. Each roam can drop calls. Two APs are probably equally weak at this desk."
    } elseif ($State.roams) {
        . $add warn 'Roamed between access points' "$($State.roams) roam(s) during the test."
    }
    if ($State.drops -and $link.wireless) { . $add bad 'The Wi-Fi connection dropped' "$($State.drops) reading(s) with no association." }

    if ($channelLoad -and $link.wireless) {
        $current = $channelLoad[$link.band] | Where-Object current | Select-Object -First 1
        $best = $channelLoad[$link.band] | Where-Object recommended | Select-Object -First 1
        if ($current -and $current.load -ge 2) {
            . $add warn "Channel $($current.channel) is crowded" (("{0} other networks overlap it (load {1:0.0})." -f $current.networks, $current.load) +
                $(if ($best) { " Channel {0} looks quieter (load {1:0.0})." -f $best.channel, $best.load }))
        }
        # A stronger AP for the same network nearby means the client is "sticky" or roaming is misconfigured
        $same = @($networks | Where-Object { $_.ssid -and $_.ssid -eq $link.ssid -and $_.bssid -ne $link.bssid })
        $stronger = $same | Where-Object { $_.signal -ge $link.signal + 8 } | Sort-Object signal -Descending | Select-Object -First 1
        if ($stronger) {
            . $add warn 'A stronger access point is in range' "Connected at $($link.signal) dBm, but $($stronger.bssid) ($($stronger.band), ch $($stronger.channel)) is at $($stronger.signal) dBm. The client is not roaming to it."
        }
        if ($link.band -eq '2.4 GHz' -and ($same | Where-Object { $_.band -ne '2.4 GHz' -and $_.signal -gt -70 })) {
            . $add warn 'Connected on 2.4 GHz although 5 GHz is available' '2.4 GHz is slower and more crowded. Band steering may be off.'
        }
    }

    $order = @{ bad = 0; warn = 1; ok = 2 }
    $findings | Sort-Object { $order[$_.level] }
}

#endregion

#region Report

function Show-Table($names, $columns) {
    $rows = foreach ($name in $names) {
        $s = $State.stats[$name]
        $row = [ordered]@{ Series = $name; '#' = $s.attempts }
        foreach ($c in $columns) { $row[$c.Substring(0, 1).ToUpper() + $c.Substring(1)] = Num $s[$c] $s.unit }
        if ($columns -contains 'jitter') { $row['Loss'] = '{0:0}%' -f ($s.loss * 100) }
        [pscustomobject]$row
    }
    Say ($rows | Format-Table -AutoSize | Out-String).TrimEnd()
}

function Show-Report($settings, $startedAt, $channelLoad, $networks, $connection) {
    $State.stats = [ordered]@{}
    foreach ($name in $State.series.Keys) { $State.stats[$name] = Get-Stats $State.series[$name] }
    $netNames = @($State.stats.Keys | Where-Object { $_ -notlike 'wifi *' })
    $wifiNames = @($State.stats.Keys | Where-Object { $_ -like 'wifi *' })
    $net = @{}; foreach ($n in $netNames) { $net[$n] = $State.stats[$n] }
    $wifi = @{}; foreach ($n in $wifiNames) { $wifi[$n] = $State.stats[$n] }

    Title 'Report' Magenta
    Say ("Test:     {0}{1}" -f $settings.name, $(if ($settings.location) { " @ $($settings.location)" }))
    Say ("Period:   {0:yyyy-MM-dd HH:mm:ss} - {1:yyyy-MM-dd HH:mm:ss}" -f $startedAt, (Get-Date))

    Title 'Findings' Magenta
    $styles = @{ bad = @('[!!]', 'Red'); warn = @('[! ]', 'Yellow'); ok = @('[ok]', 'Green') }
    foreach ($f in Get-Findings $net $wifi $channelLoad $networks $connection.link) {
        Say "$($styles[$f.level][0]) $($f.title)" $styles[$f.level][1]
        Say "     $($f.detail)"
    }

    Title 'Network' Magenta
    Show-Table $netNames @('avg', 'median', 'min', 'max', 'jitter')
    if ($wifiNames.Count) {
        Title 'Wi-Fi' Magenta
        Show-Table $wifiNames @('avg', 'median', 'min', 'max')
        Say ''
        Say ("Access points: {0}  Roams: {1}  Drops: {2}  Bands: {3}" -f (($State.bssids | Select-Object -Unique) -join ', '), $State.roams, $State.drops, ($State.bands -join ', '))
        Say 'Signal is converted from the Windows percentage (0-100% = -100..-50 dBm), so it is approximate.'
    }
}

function Show-WindowsDetails($connection) {
    Title 'Adapter' Magenta
    $a = $connection.adapter
    if ($a) {
        Say "Adapter:  $($a.InterfaceDescription)"
        Say "Driver:   $($a.DriverVersion) ($($a.DriverDate)) by $($a.DriverProvider)"
        Say "Speed:    $($a.LinkSpeed)"
    }

    # Disconnects and failed connects from the last 7 days; often the clearest sign of a flaky link
    Title 'Wi-Fi disconnects (last 7 days)' Magenta
    $events = @(Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-WLAN-AutoConfig/Operational'; Id = 8003, 8002; StartTime = (Get-Date).AddDays(-7) } -ErrorAction SilentlyContinue)
    if (-not $events.Count) {
        Say 'None found (or the event log is not readable without admin).'
        return
    }
    $events | Group-Object { $_.TimeCreated.ToString('yyyy-MM-dd') } | Sort-Object Name | ForEach-Object {
        $disconnects = @($_.Group | Where-Object Id -eq 8003).Count
        Say ('{0}  {1,3} disconnects  {2,3} failed connects' -f $_.Name, $disconnects, ($_.Count - $disconnects))
    }
    Say ''
    Say 'Latest 15:'
    foreach ($e in $events | Select-Object -First 15) {
        $message = ($e.Message -replace '\s+', ' ').Trim()  # ✔ "Reason:`r`n  The" -> "Reason: The"
        Say ('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f $e.TimeCreated, $(if ($message.Length -gt 160) { $message.Substring(0, 157) + '...' } else { $message }))
    }
    $State.raw['WLAN-AutoConfig events (latest 50)'] = ($events | Select-Object -First 50 | ForEach-Object { "$($_.TimeCreated)  [$($_.Id)]`n$($_.Message)" }) -join "`n`n"
}

# Raw command output goes to the file only, so nothing is lost when a parser misreads a translated netsh
function Save-RawOutput {
    $State.raw['netsh wlan show drivers'] = (netsh wlan show drivers) -join "`n"
    $State.raw['ipconfig /all'] = (ipconfig /all) -join "`n"
    Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value "`n`n## Raw output"
    foreach ($name in $State.raw.Keys) {
        Add-Content -LiteralPath $ReportPath -Encoding UTF8 -Value "`n### $name`n$($State.raw[$name])"
    }
}

#endregion

#region Live

function Stop-Requested {
    try {
        while ([Console]::KeyAvailable) { if ([Console]::ReadKey($true).Key -eq 'Enter') { return $true } }
    } catch {}  # Not allowed in Constrained Language Mode; Ctrl+C still stops the test and prints the report
    $false
}

function Write-ProbeRow($series, $target, $ms) {
    $link = $State.link
    $result = if ($null -eq $ms) { 'FAILED' } else { Num $ms 'ms' }
    $color = if ($null -eq $ms -or $ms -gt 300) { 'Red' } elseif ($ms -gt 150) { 'Yellow' } else { 'Gray' }
    $signal = if ($link -and $null -ne $link.signal) { "$($link.signal) dBm" } else { '-' }
    $channel = if ($link -and $link.channel) { "$($link.channel) ($($link.band))" } else { '-' }
    $before = (Fit (Get-Date -Format 'HH:mm:ss') 10) + (Fit $series 24) + (Fit $(if ($target) { $target } else { '-' }) 18)
    $after = (Fit $signal 12) + (Fit $channel 16)
    Write-Host $before -NoNewline
    Write-Host (Fit $result 10) -NoNewline -ForegroundColor $color
    Write-Host $after
    Add-Content -LiteralPath $ReportPath -Value ($before + (Fit $result 10) + $after) -Encoding UTF8
}

#endregion

#region Main

Write-Host ''
Write-Host '## Kestrel' -ForegroundColor Magenta
Write-Host '## Test settings' -ForegroundColor Cyan
$name = (Read-Host 'Test name (default: Unknown)').Trim(); if (-not $name) { $name = 'Unknown' }
$location = (Read-Host "Location, e.g. ""Anna's desk"" (optional)").Trim()
$runSpeedtests = (Read-Host 'Run speedtests? (Y/n)').Trim() -ne 'n'
$durationInput = (Read-Host 'Duration in seconds (default: 300)').Trim()
$duration = if ($durationInput -match '^\d+$') { [int]$durationInput } else { 300 }  # ✔ 120  ✘ 2m  ✘ -5
$settings = @{ name = $name; location = $location }
$ReportPath = Report-Path $name
if (-not $ReportPath) { $ReportPath = Join-Path $env:TEMP 'kestrel-report.txt' }

Assert-LocationAccess
$connection = Get-Connection
$adapterName = if ($connection.adapter) { $connection.adapter.Name } else { $null }
$connection.link = if ($connection.wireless) { Get-Link $adapterName } else { @{ wireless = $false } }
$State.link = $connection.link

Title 'Connection'
Say "Router IP: $(if ($connection.router) { $connection.router } else { 'not found' })"
Say "DNS:       $(if ($connection.dns) { $connection.dns } else { 'system resolver' })"
Say "Interface: $(if ($adapterName) { $adapterName } else { 'not found' }) ($(if ($connection.wireless) { 'wireless' } else { 'cabled' }))"
if ($connection.link.wireless) {
    $l = $connection.link
    Say "SSID:      $($l.ssid) (AP $(if ($l.bssid) { $l.bssid } else { 'unknown' }))"
    Say "Signal:    $($l.percent) (~$($l.signal) dBm)"
    Say "Channel:   $($l.channel) on $($l.band) ($($l.radio))"
    Say "Link rate: $($l.rx_rate) down / $($l.tx_rate) up Mbit/s"
} elseif (-not $connection.wireless) {
    Say 'Not on Wi-Fi: unplug the network cable / dock to test the Wi-Fi.' Yellow
}

Say ''
Say "Finding the ISP's first hop (tracert, up to ~30 s)..."
$ispHop = Find-IspHop
Say "ISP hop:   $(if ($ispHop) { $ispHop } else { 'not found (no public hop answers ping), skipped' })"

# Scan before probing starts: a scan takes the radio off-channel and would show up as latency spikes
$networks = @()
$channelLoad = $null
if ($connection.link.wireless) {
    $networks = Get-Networks
    $channelLoad = Get-ChannelLoad $networks $connection.link
    Show-Channels $channelLoad $networks
}

$pingTargets = [ordered]@{ router = $connection.router }
if ($ispHop) { $pingTargets.isp = $ispHop }
foreach ($k in $InternetTargets.Keys) { $pingTargets[$k] = $InternetTargets[$k] }
$startedAt = Get-Date
$deadline = $startedAt.AddSeconds($duration)
$job = $null
$nextSpeedtest = $startedAt.AddSeconds(20)  # Idle baseline first, like the Python engine

Say ''
Say "Running for $($duration)s. Press Enter (or Ctrl+C) to stop early."
Say ''
Say ('-' * 90)
Say ((Fit 'Time' 10) + (Fit 'Type' 24) + (Fit 'Target' 18) + (Fit 'Result' 10) + (Fit 'Signal' 12) + (Fit 'Channel' 16)) Cyan
Say ('-' * 90)

try {
    while ((Get-Date) -lt $deadline -and -not (Stop-Requested)) {
        if ($connection.wireless) {
            $link = Get-Link $adapterName
            $previous = Add-Link $link
            $State.link = $link
            if ($previous) { Say "Roamed $previous -> $($link.bssid) (ch $($link.channel), $($link.signal) dBm)" Yellow }
        }

        if ($runSpeedtests -and $job -and $job.State -ne 'Running') {
            $speeds = Receive-Job $job
            Remove-Job $job -Force
            $job = $null
            Add-Sample 'download' $speeds.download 'Mbps'
            Add-Sample 'upload' $speeds.upload 'Mbps'
            Say "Speedtest: $(Num $speeds.download 'Mbps') down / $(Num $speeds.upload 'Mbps') up" Magenta
        }
        if ($runSpeedtests -and -not $job -and (Get-Date) -ge $nextSpeedtest) {
            $job = Start-Job -ScriptBlock $SpeedtestJob
            $nextSpeedtest = (Get-Date).AddSeconds(60)
        }

        # Probes during a speedtest go in their own series: latency under load (bufferbloat) vs. idle
        foreach ($k in $pingTargets.Keys) {
            $loaded = $job -and $job.State -eq 'Running'
            $series = "ping $k" + $(if ($loaded) { ' under load' })
            $ms = Ping-Host $pingTargets[$k]
            Add-Sample $series $ms 'ms'
            Write-ProbeRow $series $pingTargets[$k] $ms
        }
        foreach ($k in $DnsTargets.Keys) {
            $loaded = $job -and $job.State -eq 'Running'
            $series = "dns $k" + $(if ($loaded) { ' under load' })
            $ms = Resolve-Timed $DnsTargets[$k] $connection.dns
            Add-Sample $series $ms 'ms'
            Write-ProbeRow $series $DnsTargets[$k] $ms
        }
        Start-Sleep -Seconds 1
    }
} finally {
    if ($job) { Remove-Job $job -Force }
    Show-Report $settings $startedAt $channelLoad $networks $connection
    Show-WindowsDetails $connection
    Save-RawOutput
    Write-Host ''
    Write-Host "Report saved to: $ReportPath" -ForegroundColor Green
    Write-Host 'Please send that file back.' -ForegroundColor Green
    try { Start-Process explorer.exe "/select,`"$ReportPath`"" } catch {}
}

#endregion
