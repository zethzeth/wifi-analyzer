// Small hand-rolled SVG charts: a time-series line chart with a crosshair, and a channel-load column chart.
const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(name, attrs = {}, parent = null) {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (parent) parent.appendChild(node);
    return node;
}

function niceTicks(min, max, count = 4) {
    if (min === max) max = min + 1;
    const rough = (max - min) / count;
    const magnitude = 10 ** Math.floor(Math.log10(rough));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough);
    const ticks = [];
    for (let v = Math.floor(min / step) * step; v < max + step; v += step) {
        ticks.push(Number(v.toFixed(6)));
        if (v >= max) break;
    }
    return ticks;
}

function formatElapsed(seconds) {
    const s = Math.max(0, Math.round(seconds));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

const Tooltip = {
    node: null,
    show(html, x, y) {
        this.node ??= document.getElementById('tooltip');
        this.node.innerHTML = html;
        this.node.hidden = false;
        const { width, height } = this.node.getBoundingClientRect();
        const left = x + 14 + width > window.innerWidth ? x - width - 14 : x + 14;
        this.node.style.left = `${left}px`;
        this.node.style.top = `${Math.max(8, Math.min(y - height / 2, window.innerHeight - height - 8))}px`;
    },
    hide() {
        if (this.node) this.node.hidden = true;
    },
};

// Shared so the latency and failure charts line up on the same time axis
const TIME_MARGIN = { l: 84, r: 84, t: 12, b: 24 };

class TimeChart {
    /**
     * Live time series on one y-axis; x is seconds since the test started. Lost samples break the line.
     *
     * @param {HTMLElement} container
     * @param {{unit: string, height?: number, yRange?: number[], floorZero?: boolean}} options
     */
    constructor(container, options) {
        this.container = container;
        this.options = { height: 220, ...options };
        this.series = [];
        this.hidden = new Set();
        this.reset(0, 60, []);
        new ResizeObserver(() => this.render()).observe(container);
    }

    reset(start, duration, series) {
        this.start = start;
        this.duration = duration;
        this.series = series;
        this.data = Object.fromEntries(series.map((s) => [s.key, []]));
        this.bands = [];
        this.markers = [];
        this.schedule();
    }

    setHidden(hidden) {
        this.hidden = hidden;
        this.schedule();
    }

    add(key, time, value) {
        this.data[key]?.push({ t: time - this.start, v: value });
        this.schedule();
    }

    openBand(time) {
        this.bands.push({ from: time - this.start, to: null });
        this.schedule();
    }

    closeBand(time) {
        const open = this.bands.findLast((b) => b.to === null);
        if (open) open.to = time - this.start;
        this.schedule();
    }

    mark(time) {
        this.markers.push(time - this.start);
        this.schedule();
    }

    schedule() {
        if (this.pending) return;
        this.pending = true;
        requestAnimationFrame(() => {
            this.pending = false;
            this.render();
        });
    }

    get visible() {
        return this.series.filter((s) => !this.hidden.has(s.key));
    }

    latest() {
        return Math.max(0, ...this.series.flatMap((s) => this.data[s.key].map((p) => p.t)));
    }

    render() {
        const { unit, height, yRange, floorZero } = this.options;
        const width = this.container.clientWidth;
        if (!width) return;
        const m = TIME_MARGIN;
        const plotW = width - m.l - m.r;
        const plotH = height - m.t - m.b;
        const visible = this.visible;

        const values = visible.flatMap((s) => this.data[s.key].map((p) => p.v)).filter((v) => v !== null);
        let lo = floorZero ? 0 : Math.min(...values, yRange?.[0] ?? Infinity);
        let hi = Math.max(...values, yRange?.[1] ?? -Infinity);
        if (!Number.isFinite(lo) || !Number.isFinite(hi)) [lo, hi] = yRange ?? [0, 50];
        const ticks = niceTicks(lo, hi === lo ? lo + 10 : hi);
        [lo, hi] = [ticks[0], ticks.at(-1)];

        const latest = this.latest();
        const span = Math.max(this.duration, latest, 1);
        const x = (t) => m.l + (t / span) * plotW;
        const y = (v) => m.t + (1 - (v - lo) / (hi - lo)) * plotH;

        const svg = svgEl('svg', { class: 'viz', width, height, role: 'img', 'aria-label': `${unit} over time` });
        drawBands(svg, this.bands, x, latest, m.t, plotH);
        for (const tick of ticks) {
            svgEl('line', { class: tick === lo ? 'baseline' : 'grid', x1: m.l, x2: width - m.r, y1: y(tick), y2: y(tick) }, svg);
            svgEl('text', { x: m.l - 8, y: y(tick) + 4, 'text-anchor': 'end' }, svg).textContent = `${tick}`;
        }
        drawTimeAxis(svg, x, span, height);
        for (const t of this.markers) {
            svgEl('line', { class: 'marker', x1: x(t), x2: x(t), y1: m.t, y2: m.t + plotH }, svg);
        }

        for (const s of visible) {
            let d = '';
            let pen = false;
            for (const p of this.data[s.key]) {
                if (p.v === null) {
                    pen = false;
                    continue;
                }
                d += `${pen ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`;
                pen = true;
            }
            if (d) svgEl('path', { class: `line ${s.cls}`, d }, svg);
        }

        // End dots + direct labels, nudged apart so they don't collide
        const ends = visible
            .map((s) => ({ s, p: this.data[s.key].findLast((p) => p.v !== null) }))
            .filter((e) => e.p)
            .sort((a, b) => y(a.p.v) - y(b.p.v));
        const labelYs = spreadLabels(ends.map(({ p }) => y(p.v) + 4), 13, m.t + 8, m.t + plotH);
        ends.forEach(({ s, p }, i) => {
            svgEl('circle', { class: `dot ${s.cls}`, cx: x(p.t), cy: y(p.v), r: 4 }, svg);
            if (this.series.length > 1) {
                svgEl('text', { class: 'label', x: x(p.t) + 9, y: labelYs[i] }, svg).textContent = s.label;
            }
        });

        this.attachHover(svg, { m, plotW, plotH, x, y, span });
        this.container.replaceChildren(svg);
    }

    attachHover(svg, { m, plotW, plotH, x, y, span }) {
        const { unit } = this.options;
        const layer = svgEl('g', {}, svg);
        const hit = svgEl('rect', { x: m.l, y: m.t, width: plotW, height: plotH, fill: 'transparent' }, svg);
        hit.addEventListener('mousemove', (event) => {
            const t = ((event.clientX - svg.getBoundingClientRect().left - m.l) / plotW) * span;
            const hits = this.visible
                .map((s) => ({ s, p: nearest(this.data[s.key], t) }))
                .filter(({ p }) => p && Math.abs(p.t - t) <= Math.max(5, span / 60));
            layer.replaceChildren();
            if (!hits.length) return Tooltip.hide();
            svgEl('line', { class: 'crosshair', x1: x(t), x2: x(t), y1: m.t, y2: m.t + plotH }, layer);
            const rows = hits.map(({ s, p }) => {
                if (p.v !== null) svgEl('circle', { class: `dot ${s.cls}`, cx: x(p.t), cy: y(p.v), r: 4 }, layer);
                const value = p.v === null ? '<span class="lost">✕ failed</span>' : `${Math.round(p.v)} ${unit}`;
                return `<div class="row"><b>${value}</b><span>${s.label}<i class="key key-${s.cls}"></i></span></div>`;
            });
            Tooltip.show(`<div class="head">${formatElapsed(t)} in</div>${rows.join('')}`, event.clientX, event.clientY);
        });
        hit.addEventListener('mouseleave', () => {
            layer.replaceChildren();
            Tooltip.hide();
        });
    }
}

class FailureChart {
    /**
     * One row per target on the same time axis as TimeChart; each failed call is a tick in its row.
     *
     * @param {HTMLElement} container
     */
    constructor(container) {
        this.container = container;
        this.hidden = new Set();
        this.reset(0, 60, []);
        new ResizeObserver(() => this.render()).observe(container);
    }

    /**
     * @param {number} start
     * @param {number} duration
     * @param {{key: string, label: string}[]} rows
     */
    reset(start, duration, rows) {
        this.start = start;
        this.duration = duration;
        this.rows = rows;
        this.failures = Object.fromEntries(rows.map((r) => [r.key, []]));
        this.attempts = Object.fromEntries(rows.map((r) => [r.key, 0]));
        this.bands = [];
        this.latestT = 0;
        this.schedule();
    }

    setHidden(hidden) {
        this.hidden = hidden;
        this.schedule();
    }

    add(key, time, failed, detail) {
        if (!(key in this.attempts)) return;
        const t = time - this.start;
        this.attempts[key] += 1;
        this.latestT = Math.max(this.latestT, t);
        if (failed) this.failures[key].push({ t, detail });
        this.schedule();
    }

    openBand(time) {
        this.bands.push({ from: time - this.start, to: null });
        this.schedule();
    }

    closeBand(time) {
        const open = this.bands.findLast((b) => b.to === null);
        if (open) open.to = time - this.start;
        this.schedule();
    }

    schedule() {
        TimeChart.prototype.schedule.call(this);
    }

    render() {
        const width = this.container.clientWidth;
        if (!width) return;
        const rows = this.rows.filter((r) => !this.hidden.has(r.key));
        const rowH = 26;
        const m = TIME_MARGIN;
        const plotW = width - m.l - m.r;
        const plotH = Math.max(rowH, rows.length * rowH);
        const height = m.t + plotH + m.b;
        const span = Math.max(this.duration, this.latestT, 1);
        const x = (t) => m.l + (t / span) * plotW;

        const svg = svgEl('svg', { class: 'viz', width, height, role: 'img', 'aria-label': 'Failed calls over time' });
        drawBands(svg, this.bands, x, this.latestT, m.t, plotH);
        drawTimeAxis(svg, x, span, height);

        rows.forEach((row, i) => {
            const top = m.t + i * rowH;
            const mid = top + rowH / 2;
            svgEl('line', { class: 'grid', x1: m.l, x2: width - m.r, y1: top + rowH, y2: top + rowH }, svg);
            svgEl('text', { x: m.l - 8, y: mid + 4, 'text-anchor': 'end' }, svg).textContent = row.label;
            for (const f of this.failures[row.key]) {
                svgEl('rect', { class: 'fail-mark', x: x(f.t) - 1.5, y: mid - 7, width: 3, height: 14, rx: 1 }, svg);
            }
            const lost = this.failures[row.key].length;
            const count = svgEl('text', { class: lost ? 'label lost' : '', x: width - m.r + 10, y: mid + 4 }, svg);
            count.textContent = `${lost} of ${this.attempts[row.key]}`;
        });
        svgEl('line', { class: 'baseline', x1: m.l, x2: width - m.r, y1: m.t + plotH, y2: m.t + plotH }, svg);

        // Hover a row: list the failures near the pointer
        const layer = svgEl('g', {}, svg);
        const hit = svgEl('rect', { x: m.l, y: m.t, width: plotW, height: plotH, fill: 'transparent' }, svg);
        hit.addEventListener('mousemove', (event) => {
            const box = svg.getBoundingClientRect();
            const t = ((event.clientX - box.left - m.l) / plotW) * span;
            const row = rows[Math.floor((event.clientY - box.top - m.t) / rowH)];
            layer.replaceChildren();
            if (!row) return Tooltip.hide();
            svgEl('line', { class: 'crosshair', x1: x(t), x2: x(t), y1: m.t, y2: m.t + plotH }, layer);
            const near = this.failures[row.key].filter((f) => Math.abs(f.t - t) <= Math.max(5, span / 50));
            const lines = near.slice(0, 8).map((f) => `<div class="row"><b class="lost">✕ ${formatElapsed(f.t)}</b><span>${f.detail}</span></div>`);
            Tooltip.show(
                `<div class="head">${row.label} · ${this.failures[row.key].length} of ${this.attempts[row.key]} failed</div>`
                + (lines.join('') || '<div class="row"><span>No failures here</span></div>')
                + (near.length > 8 ? `<div class="row"><span>+${near.length - 8} more</span></div>` : ''),
                event.clientX, event.clientY,
            );
        });
        hit.addEventListener('mouseleave', () => {
            layer.replaceChildren();
            Tooltip.hide();
        });
        this.container.replaceChildren(svg);
    }
}

// Pushes sorted label positions apart by `gap`, keeping them all between `top` and `bottom`
function spreadLabels(ys, gap, top, bottom) {
    const out = [...ys];
    for (let i = 0; i < out.length; i++) out[i] = Math.max(out[i], i ? out[i - 1] + gap : top);
    for (let i = out.length - 1; i >= 0; i--) out[i] = Math.min(out[i], i < out.length - 1 ? out[i + 1] - gap : bottom);
    return out;
}

function drawBands(svg, bands, x, latest, top, height) {
    for (const band of bands) {
        const end = band.to ?? latest;
        svgEl('rect', { class: 'band', x: x(band.from), y: top, width: Math.max(1, x(end) - x(band.from)), height }, svg);
    }
}

function drawTimeAxis(svg, x, span, height) {
    for (const t of niceTicks(0, span, 5).filter((t) => t <= span)) {
        svgEl('text', { x: x(t), y: height - 6, 'text-anchor': 'middle' }, svg).textContent = formatElapsed(t);
    }
}

function nearest(points, t) {
    let best = null;
    for (const p of points) {
        if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
    }
    return best;
}

/**
 * Column chart of channel load for one band; the current channel gets its own colour.
 *
 * @param {HTMLElement} container
 * @param {{channel: number, load: number, radios: number, strongest: ?number, current: boolean, recommended: boolean}[]} loads
 */
function renderChannelChart(container, loads) {
    const width = container.clientWidth;
    if (!width) return;
    const height = 200;
    const m = { l: 36, r: 8, t: 22, b: 24 };
    const plotW = width - m.l - m.r;
    const plotH = height - m.t - m.b;
    const ticks = niceTicks(0, Math.max(1, ...loads.map((l) => l.load)), 4);
    const hi = ticks.at(-1);
    const slot = plotW / loads.length;
    const barW = Math.min(24, slot - 2);
    const y = (v) => m.t + (1 - v / hi) * plotH;
    const everyOther = slot < 22;

    const svg = svgEl('svg', { class: 'viz', width, height, role: 'img', 'aria-label': 'Load per channel' });
    for (const tick of ticks) {
        svgEl('line', { class: tick === 0 ? 'baseline' : 'grid', x1: m.l, x2: width - m.r, y1: y(tick), y2: y(tick) }, svg);
        svgEl('text', { x: m.l - 8, y: y(tick) + 4, 'text-anchor': 'end' }, svg).textContent = tick;
    }

    loads.forEach((load, i) => {
        const cx = m.l + slot * i + slot / 2;
        const barH = (load.load / hi) * plotH;
        if (barH > 0.5) {
            svgEl('path', { class: `bar${load.current ? ' current' : ''}`, d: columnPath(cx - barW / 2, y(load.load), barW, barH) }, svg);
        }
        if (!everyOther || i % 2 === 0 || load.current || load.recommended) {
            svgEl('text', { x: cx, y: height - 6, 'text-anchor': 'middle', class: load.current ? 'label' : '' }, svg).textContent = load.channel;
        }
        const tag = load.current ? 'you' : load.recommended ? '★ quietest' : '';
        if (tag) {
            svgEl('text', { class: 'label', x: cx, y: y(load.load) - 6, 'text-anchor': 'middle' }, svg).textContent = tag;
        }

        const hit = svgEl('rect', { class: 'hit', x: cx - slot / 2, y: m.t, width: slot, height: plotH }, svg);
        hit.addEventListener('mousemove', (event) => {
            const notes = [load.current && 'Your channel', load.recommended && 'Quietest candidate'].filter(Boolean);
            Tooltip.show(
                `<div class="head">Channel ${load.channel}</div>`
                + `<div class="row"><span>Load</span><b>${load.load.toFixed(1)}</b></div>`
                + `<div class="row"><span>Overlapping radios</span><b>${load.radios}</b></div>`
                + `<div class="row"><span>Loudest</span><b>${load.strongest ?? '–'} ${load.strongest === null ? '' : 'dBm'}</b></div>`
                + notes.map((n) => `<div class="row"><span>${n}</span></div>`).join(''),
                event.clientX, event.clientY,
            );
        });
        hit.addEventListener('mouseleave', () => Tooltip.hide());
    });

    container.replaceChildren(svg);
}

// Rounded data-end, square at the baseline
function columnPath(x, y, w, h, r = 4) {
    r = Math.min(r, h, w / 2);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}
