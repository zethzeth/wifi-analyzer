// Renderer: sends commands to the Python engine and draws whatever events come back.
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const fmt = (value, unit = '', digits = 0) => (value === null || value === undefined ? '–' : `${Number(value).toFixed(digits)}${unit && ' ' + unit}`);

// Colour follows the target, so hiding one never repaints the others
const SERIES_STYLE = {
    router: { label: 'Router', cls: 's1' },
    isp: { label: 'ISP hop', cls: 's2' },
    google: { label: 'Google', cls: 's3' },
    cloudflare: { label: 'Cloudflare', cls: 's4' },
    dr: { label: 'dr.dk', cls: 's5' },
};
const LEVEL_ICONS = { bad: '✕', warn: '!', ok: '✓' };
const LINK_LABELS = { signal: 'Signal', noise: 'Noise', snr: 'SNR', tx_rate: 'Link rate' };
const MAX_CALL_ROWS = 500;

const latencyChart = new TimeChart($('latency-chart'), { unit: 'ms', floorZero: true });
const failureChart = new FailureChart($('failure-chart'));
const signalChart = new TimeChart($('signal-chart'), { unit: 'dBm', height: 170, yRange: [-80, -40] });
const SIGNAL_SERIES = [{ key: 'signal', label: 'Signal', cls: 's1' }];

let test = null; // Live tallies for the running (or last) test
let running = false;
let lastChannels = null;
let pingSeries = []; // [{key, label, cls, host}] for the current test
let hidden = new Set(); // Ping targets toggled off in the chips row
let resultsView = 'per-target';

// Tabs
for (const tab of document.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === tab));
        document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${tab.dataset.tab}`));
        if (tab.dataset.tab === 'channels' && lastChannels) renderChannels(lastChannels);
    });
}

$('test-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    window.kestrel.send({
        cmd: 'start',
        settings: {
            test_name: `${form.get('test_name') || 'Desk check'} - ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`,
            location: form.get('location') || '',
            duration: Number(form.get('duration')),
            run_speedtests: form.get('run_speedtests') === 'on',
        },
    });
    setRunning(true);
    $('progress').hidden = false;
    $('progress-text').textContent = 'Finding the ISP hop and scanning…';
});
$('stop').addEventListener('click', () => {
    window.kestrel.send({ cmd: 'stop' });
    $('stop').disabled = true;
    $('stop').textContent = 'Stopping…';
});
$('scan').addEventListener('click', () => {
    $('scan').disabled = true;
    $('scan').textContent = 'Scanning…';
    window.kestrel.send({ cmd: 'scan', rescan: true });
});
$('refresh').addEventListener('click', () => window.kestrel.send({ cmd: 'connection' }));

// Target chips: click toggles one, double-click shows only that one
$('chips').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    hidden.has(chip.dataset.key) ? hidden.delete(chip.dataset.key) : hidden.add(chip.dataset.key);
    applyFilter();
});
$('chips').addEventListener('dblclick', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    hidden = new Set(pingSeries.map((s) => s.key).filter((key) => key !== chip.dataset.key));
    applyFilter();
});
$('show-all').addEventListener('click', () => {
    hidden = new Set();
    applyFilter();
});

for (const button of document.querySelectorAll('.segmented button')) {
    button.addEventListener('click', () => {
        resultsView = button.dataset.view;
        document.querySelectorAll('.segmented button').forEach((b) => b.classList.toggle('active', b === button));
        $('only-failures-wrap').hidden = resultsView !== 'every-call';
        renderResults();
    });
}
$('only-failures').addEventListener('change', () => renderResults());

const handlers = {
    connection: (data) => renderConnection(data),
    started: (data) => startTest(data),
    link: (data) => onLink(data),
    probe: (data) => onProbe(data),
    roam: (data) => {
        test.roams += 1;
        signalChart.mark(data.time);
        addEvent(data.time, 'Roamed', `${esc(data.from)} → ${esc(data.to)} (ch ${data.channel}, ${data.signal} dBm)`);
        renderTiles();
    },
    speedtest_started: (data) => {
        latencyChart.openBand(data.time);
        failureChart.openBand(data.time);
        addEvent(data.time, 'Speedtest', 'Started, the link is now under load');
    },
    speedtest: (data) => {
        latencyChart.closeBand(data.time);
        failureChart.closeBand(data.time);
        test.speed = data;
        addEvent(data.time, 'Speedtest', `${fmt(data.download, 'Mbps')} down / ${fmt(data.upload, 'Mbps')} up`);
        renderTiles();
    },
    channels: (data) => {
        lastChannels = data;
        renderChannels(data);
    },
    notice: (data) => addEvent(Date.now() / 1000, 'Note', esc(data.message)),
    report: (data) => renderReport(data),
    idle: () => setRunning(false),
    error: (data) => addEvent(Date.now() / 1000, 'Error', esc(data.message)),
    engine_exit: (data) => addEvent(Date.now() / 1000, 'Error', `The engine stopped (exit code ${data.code}). Restart the app.`),
};

window.kestrel.onEvent(({ event, data }) => handlers[event]?.(data));
window.kestrel.send({ cmd: 'connection' });

function setRunning(isRunning) {
    running = isRunning;
    $('start').hidden = isRunning;
    $('stop').hidden = !isRunning;
    $('stop').disabled = false;
    $('stop').textContent = 'Stop';
    $('scan').disabled = isRunning;
    $('scan-note').textContent = isRunning
        ? 'Scanning is paused while a test runs: it takes the radio off-channel and would show up as latency spikes.'
        : 'Load = signal-weighted count of other radios overlapping a channel. A loud neighbour counts ~1, a faint one ~0.';
    document.querySelectorAll('#test-form input, #test-form select').forEach((input) => (input.disabled = isRunning));
    if (!isRunning) $('progress-text').textContent = 'Finished';
}

function startTest({ settings, connection, targets, dns_targets: dnsTargets, started_at: startedAt }) {
    pingSeries = Object.entries(targets).map(([key, host]) => ({
        key, host, ...(SERIES_STYLE[key] ?? { label: key, cls: 's1' }),
    }));
    const tally = () => ({ idle: [], loaded: [], lost: 0, total: 0, last: undefined });
    test = {
        startedAt,
        duration: settings.duration,
        pings: Object.fromEntries(pingSeries.map((s) => [s.key, tally()])),
        dns: Object.fromEntries(Object.entries(dnsTargets).map(([name, host]) => [name, { ...tally(), host }])),
        calls: [],
        signal: null,
        roams: 0,
        speed: null,
    };
    hidden = new Set([...hidden].filter((key) => key in targets));
    latencyChart.reset(startedAt, settings.duration, pingSeries);
    failureChart.reset(startedAt, settings.duration, [
        ...pingSeries.map((s) => ({ key: `ping:${s.key}`, label: s.label })),
        ...Object.keys(dnsTargets).map((name) => ({ key: `dns:${name}`, label: `DNS ${name}` })),
    ]);
    signalChart.reset(startedAt, settings.duration, SIGNAL_SERIES);
    $('events').innerHTML = '';
    $('report-card').hidden = true;
    $('filters').hidden = false;
    renderConnection(connection);
    applyFilter();
    renderTiles();
    tickProgress();
}

function applyFilter() {
    latencyChart.setHidden(hidden);
    failureChart.setHidden(new Set([...hidden].map((key) => `ping:${key}`)));
    $('chips').innerHTML = pingSeries.map((s) => `
        <button class="chip" type="button" data-key="${s.key}" aria-pressed="${!hidden.has(s.key)}">
            <i class="key key-${s.cls}"></i>${s.label}<span class="host">${esc(s.host ?? 'not found')}</span>
        </button>`).join('');
    $('latency-legend').innerHTML = pingSeries.filter((s) => !hidden.has(s.key))
        .map((s) => `<span><i class="key key-${s.cls}"></i>${s.label}</span>`).join('');
    renderResults();
}

function tickProgress() {
    if (!running || !test) return;
    const elapsed = Date.now() / 1000 - test.startedAt;
    $('progress-fill').style.width = `${Math.min(100, (elapsed / test.duration) * 100)}%`;
    $('progress-text').textContent = `${formatElapsed(elapsed)} of ${formatElapsed(test.duration)}`;
    setTimeout(tickProgress, 500);
}

function onLink(link) {
    if (!test) return;
    test.signal = link.signal;
    signalChart.add('signal', link.time, link.signal ?? null);
    renderConnection({ ...lastConnection, link });
    renderTiles();
}

function onProbe(probe) {
    if (!test) return;
    const tally = probe.kind === 'ping' ? test.pings[probe.name] : test.dns[probe.name];
    if (tally) {
        tally.total += 1;
        tally.last = probe.ms;
        if (probe.ms === null) tally.lost += 1;
        else (probe.loaded ? tally.loaded : tally.idle).push(probe.ms);
    }
    test.calls.push(probe);
    if (probe.kind === 'ping') latencyChart.add(probe.name, probe.time, probe.ms);
    failureChart.add(`${probe.kind}:${probe.name}`, probe.time, probe.ms === null, esc(probe.target ?? 'no host'));
    if (probe.ms !== null && probe.ms > 150) {
        addEvent(probe.time, 'Spike', `${esc(probe.kind)} ${esc(probe.name)}: ${Math.round(probe.ms)} ms${probe.loaded ? ' (during speedtest)' : ''}`);
    }
    renderTilesSoon();
    renderResultsSoon();
}

let resultsPending = false;
function renderResultsSoon() {
    if (resultsPending) return;
    resultsPending = true;
    setTimeout(() => {
        resultsPending = false;
        renderResults();
    }, 1000);
}

function renderResults() {
    if (!test) {
        $('results-table').innerHTML = '<tr><td class="muted">Start a test to see results.</td></tr>';
        return;
    }
    resultsView === 'per-target' ? renderPerTarget() : renderEveryCall();
}

function renderPerTarget() {
    const rows = [
        ...pingSeries.filter((s) => !hidden.has(s.key)).map((s) => ({ name: `<i class="key key-${s.cls}"></i>Ping ${s.label}`, host: s.host, t: test.pings[s.key] })),
        ...Object.entries(test.dns).map(([name, t]) => ({ name: `DNS ${esc(name)}`, host: t.host, t })),
    ];
    $('results-table').innerHTML = `
        <tr><th>Target</th><th>Host</th><th class="num">Sent</th><th class="num">Failed</th><th class="num">Loss</th>
        <th class="num">Last</th><th class="num">Median idle</th><th class="num">Median under load</th><th class="num">Max</th><th class="num">Jitter</th></tr>`
        + rows.map(({ name, host, t }) => {
            const ok = [...t.idle, ...t.loaded];
            const failed = t.lost ? `<span class="lost">✕ ${t.lost}</span>` : '0';
            const last = t.last === null ? '<span class="lost">✕ failed</span>' : fmt(t.last, 'ms');
            return `<tr class="${t.lost ? 'has-failures' : ''}"><td>${name}</td><td>${esc(host ?? '–')}</td><td class="num">${t.total}</td>
                <td class="num">${failed}</td><td class="num">${t.total ? fmt((t.lost / t.total) * 100, '%', 1) : '–'}</td>
                <td class="num">${last}</td><td class="num">${fmt(median(t.idle), 'ms')}</td><td class="num">${fmt(median(t.loaded), 'ms')}</td>
                <td class="num">${fmt(ok.length ? Math.max(...ok) : null, 'ms')}</td><td class="num">${fmt(jitter(t.idle), 'ms')}</td></tr>`;
        }).join('');
    $('results-caption').textContent = 'Failed = no answer within 3 seconds. "Idle" excludes calls made while a speedtest loaded the link; "under load" is only those. Jitter = average change between consecutive idle pings.';
}

function renderEveryCall() {
    const onlyFailures = $('only-failures').checked;
    const calls = test.calls.filter((c) => !(c.kind === 'ping' && hidden.has(c.name)) && (!onlyFailures || c.ms === null));
    const shown = calls.slice(-MAX_CALL_ROWS).reverse();
    $('results-table').innerHTML = `
        <tr><th>Time</th><th class="num">Into test</th><th>Call</th><th>Host</th><th class="num">Result</th><th>Link</th></tr>`
        + shown.map((c) => {
            const style = c.kind === 'ping' ? SERIES_STYLE[c.name] : null;
            const label = c.kind === 'ping' ? `<i class="key key-${style?.cls ?? 's1'}"></i>Ping ${style?.label ?? esc(c.name)}` : `DNS ${esc(c.name)}`;
            const result = c.ms === null ? '<span class="lost">✕ failed</span>' : fmt(c.ms, 'ms');
            return `<tr class="${c.ms === null ? 'has-failures' : ''}"><td>${c.clock}</td><td class="num">${formatElapsed(c.time - test.startedAt)}</td>
                <td>${label}</td><td>${esc(c.target ?? '–')}</td><td class="num">${result}</td><td>${c.loaded ? 'under load' : 'idle'}</td></tr>`;
        }).join('')
        + (shown.length ? '' : `<tr><td colspan="6" class="muted">${onlyFailures ? 'No failed calls.' : 'No calls yet.'}</td></tr>`);
    $('results-caption').textContent = calls.length > MAX_CALL_ROWS
        ? `Showing the ${MAX_CALL_ROWS} newest of ${calls.length} calls. Every call is also saved in kestrel.db.`
        : 'Newest first. Every call is also saved in kestrel.db.';
}

function jitter(values) {
    if (values.length < 2) return null;
    return values.slice(1).reduce((sum, v, i) => sum + Math.abs(v - values[i]), 0) / (values.length - 1);
}

let tilesPending = false;
function renderTilesSoon() {
    if (tilesPending) return;
    tilesPending = true;
    setTimeout(() => {
        tilesPending = false;
        renderTiles();
    }, 400);
}

function renderTiles() {
    if (!test) {
        $('tiles').innerHTML = '';
        return;
    }
    const router = test.pings.router ?? { idle: [] };
    const internet = test.pings.google ?? { idle: [] };
    const lost = Object.values(test.pings).reduce((sum, p) => sum + p.lost, 0);
    const total = Object.values(test.pings).reduce((sum, p) => sum + p.total, 0);
    const lossPct = total ? (lost / total) * 100 : null;

    $('tiles').innerHTML = [
        tile('Router ping', fmt(median(router.idle), 'ms'), latencyStatus(median(router.idle), 10, 30), 'median, idle'),
        tile('Internet ping', fmt(median(internet.idle), 'ms'), latencyStatus(median(internet.idle), 50, 100), 'median to 8.8.8.8, idle'),
        tile('Packet loss', lossPct === null ? '–' : `${lossPct.toFixed(1)} %`, lossPct === null ? null : lossPct === 0 ? ['good', 'None'] : lossPct < 2 ? ['warn', 'Some'] : ['bad', 'High'], `${lost} of ${total} pings`),
        tile('Signal', fmt(test.signal, 'dBm'), signalStatus(test.signal), 'latest reading'),
        tile('Roams', String(test.roams), test.roams === 0 ? ['good', 'Stable'] : test.roams < 3 ? ['warn', 'Some'] : ['bad', 'Flapping'], 'access-point switches'),
        tile('Speed', test.speed ? `${fmt(test.speed.download)} / ${fmt(test.speed.upload)}` : '–', null, 'Mbps down / up, last run'),
    ].join('');
}

function tile(label, value, status, sub) {
    const badge = status ? `<span class="status ${status[0]}"><span class="dot"></span>${status[1]}</span>` : '';
    return `<div class="tile"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${badge} ${sub}</div></div>`;
}

function latencyStatus(ms, good, bad) {
    if (ms === null) return null;
    return ms <= good ? ['good', 'Good'] : ms <= bad ? ['warn', 'Fair'] : ['bad', 'Poor'];
}

function signalStatus(dbm) {
    if (dbm === null || dbm === undefined) return null;
    return dbm >= -60 ? ['good', 'Excellent'] : dbm >= -67 ? ['good', 'Good'] : dbm >= -75 ? ['warn', 'Fair'] : ['bad', 'Poor'];
}

function median(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function addEvent(time, kind, html) {
    const list = $('events');
    if (list.firstElementChild?.classList.contains('muted')) list.innerHTML = '';
    const clock = new Date(time * 1000).toLocaleTimeString([], { hour12: false });
    list.insertAdjacentHTML('afterbegin', `<li><time>${clock}</time><b>${kind}</b><span>${html}</span></li>`);
    while (list.children.length > 300) list.lastElementChild.remove();
}

let lastConnection = null;
function renderConnection(connection) {
    lastConnection = connection;
    const link = connection.link;
    const parts = [];
    if (link.wireless) {
        parts.push(`<span>Network <b>${esc(link.ssid ?? 'hidden')}</b></span>`);
        parts.push(`<span>AP <b>${esc(link.bssid ?? 'unknown')}</b></span>`);
        parts.push(`<span>Channel <b>${link.channel ?? '–'}</b> · ${esc(link.band ?? '')} · ${link.width ?? '–'} MHz</span>`);
        parts.push(`<span>Signal <b>${fmt(link.signal, 'dBm')}</b>${link.noise ? ` · SNR ${link.snr} dB` : ''}</span>`);
        parts.push(`<span>Rate <b>${fmt(link.tx_rate, 'Mbit/s')}</b></span>`);
    } else {
        parts.push(`<span>Cabled <b>${esc(link.interface ?? 'unknown interface')}</b></span>`);
    }
    parts.push(`<span>Router <b>${esc(connection.router_ip ?? 'not found')}</b></span>`);
    parts.push(`<span>DNS <b>${esc(connection.dns_server ?? 'system')}</b></span>`);
    $('conn').innerHTML = parts.join('');
}

function renderReport(report) {
    const { summary, findings, settings } = report;
    $('report-card').hidden = false;
    $('report-meta').textContent = `${settings.test_name}${settings.location ? ' @ ' + settings.location : ''}`;
    $('findings').innerHTML = findings.map((f) => `
        <li class="finding ${f.level}">
            <span class="icon" aria-label="${f.level}">${LEVEL_ICONS[f.level]}</span>
            <span class="title">${esc(f.title)}</span>
            <span class="detail">${esc(f.detail)}</span>
        </li>`).join('') || '<li class="muted">No findings.</li>';

    const rows = Object.entries(summary.network).map(([name, s]) => `
        <tr><td>${esc(name)}</td><td class="num">${s.attempts}</td><td class="num">${fmt(s.avg, s.unit)}</td>
        <td class="num">${fmt(s.median, s.unit)}</td><td class="num">${fmt(s.max, s.unit)}</td>
        <td class="num">${fmt(s.jitter, s.unit)}</td><td class="num">${fmt(s.loss * 100, '%', 1)}</td></tr>`);
    const linkRows = Object.entries(summary.link).map(([name, s]) => `
        <tr><td>${LINK_LABELS[name] ?? esc(name)}</td><td class="num">${s.attempts}</td><td class="num">${fmt(s.avg, s.unit)}</td>
        <td class="num">${fmt(s.median, s.unit)}</td><td class="num">${fmt(s.min, s.unit)} – ${fmt(s.max, s.unit)}</td><td></td><td></td></tr>`);
    $('summary-table').innerHTML = `
        <tr><th></th><th class="num">#</th><th class="num">Avg</th><th class="num">Median</th><th class="num">Max / range</th>
        <th class="num">Jitter</th><th class="num">Loss</th></tr>${rows.join('')}${linkRows.join('')}`;
    $('report-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderChannels(report) {
    $('scan').disabled = running;
    $('scan').textContent = 'Scan now';
    const current = report.current;
    $('bands').innerHTML = Object.keys(report.bands).map((band, i) => `
        <div class="card">
            <div class="band-head">
                <h3>${esc(band)}</h3>
                <span class="muted">${bandSummary(report.bands[band], current, band)}</span>
                <div class="legend"><span><i class="sq swatch-1"></i>Other channels</span><span><i class="sq swatch-2"></i>Your channel</span></div>
            </div>
            <div class="chart" id="band-${i}"></div>
        </div>`).join('');
    // Charts only measure their width once visible; a hidden tab re-renders when opened
    Object.values(report.bands).forEach((loads, i) => renderChannelChart($(`band-${i}`), loads));

    lastNetworks = report.networks;
    renderNetworks();
}

let lastNetworks = [];

// Comma-separated substrings; an access point shows if its SSID or BSSID contains any of them
function networkMatcher() {
    const caseSensitive = $('ap-case').checked;
    const norm = (text) => (caseSensitive ? text : text.toLowerCase());
    const terms = $('ap-filter').value.split(',').map((t) => norm(t.trim())).filter(Boolean);
    if (!terms.length) return () => true;
    return (n) => terms.some((term) => norm(n.ssid ?? '').includes(term) || norm(n.bssid ?? '').includes(term));
}

function renderNetworks() {
    const matches = networkMatcher();
    const networks = lastNetworks.filter(matches);
    $('network-count').textContent = networks.length === lastNetworks.length
        ? `${lastNetworks.length} found`
        : `${networks.length} of ${lastNetworks.length} shown`;
    $('networks').innerHTML = `<tr><th>SSID</th><th>BSSID</th><th>Band</th><th class="num">Channel</th><th class="num">Width</th><th>Signal</th></tr>`
        + networks.map((n) => `
        <tr class="${n.in_use ? 'in-use' : ''}">
            <td>${n.ssid ? esc(n.ssid) : '<span class="muted">(hidden)</span>'}${n.in_use ? ' · connected' : ''}</td>
            <td>${esc(n.bssid ?? '–')}</td><td>${esc(n.band)}</td><td class="num">${n.channel}</td><td class="num">${n.width} MHz</td>
            <td><span class="meter"><i data-width="${signalPercent(n.signal)}"></i></span>${n.signal} dBm</td>
        </tr>`).join('')
        + (networks.length || !lastNetworks.length ? '' : '<tr><td colspan="6" class="muted">No access points match the filter.</td></tr>');
    // CSP blocks inline style attributes, so widths are set through the CSSOM
    document.querySelectorAll('#networks [data-width]').forEach((bar) => (bar.style.width = `${bar.dataset.width}%`));
}

// The filter survives restarts; storage can be unavailable, so it's best-effort
try {
    $('ap-filter').value = localStorage.getItem('kestrel.apFilter') ?? '';
    $('ap-case').checked = localStorage.getItem('kestrel.apCase') === '1';
} catch {}
$('ap-filter').addEventListener('input', () => {
    try { localStorage.setItem('kestrel.apFilter', $('ap-filter').value); } catch {}
    renderNetworks();
});
$('ap-case').addEventListener('change', () => {
    try { localStorage.setItem('kestrel.apCase', $('ap-case').checked ? '1' : '0'); } catch {}
    renderNetworks();
});

function bandSummary(loads, current, band) {
    const best = loads.find((l) => l.recommended);
    const mine = current?.band === band ? loads.find((l) => l.current) : null;
    const parts = [];
    if (mine) parts.push(`You're on ${mine.channel} (load ${mine.load.toFixed(1)}, ${mine.radios} other radios)`);
    if (best) parts.push(`quietest: ${best.channel} (load ${best.load.toFixed(1)})`);
    return parts.join(' · ');
}

function signalPercent(dbm) {
    return Math.max(0, Math.min(100, ((dbm + 95) / 65) * 100));
}

renderTiles();
