<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link
		href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Rajdhani:wght@500;700&family=DM+Sans:wght@400;500;600&display=swap"
		rel="stylesheet"
	/>
</svelte:head>

<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	type Price = { symbol: string; price: number; updated_at: string; total_trades: number; total_volume: number };
	type Trade = { trade_id: number; symbol: string; price: number; quantity: number; notional: number; buyer_maker: boolean; trade_time: string };

	let prices        = $state<Price[]>([]);
	let trades        = $state<Trade[]>([]);
	let connected     = $state(false);
	let clock         = $state('');
	let prevPrices    = $state<Record<string, number>>({});
	let flashDir      = $state<Record<string, string>>({});
	let priceHistory  = $state<Record<string, number[]>>({});
	let interval: ReturnType<typeof setInterval>;

	const HISTORY_MAX = 80;

	const META: Record<string, { name: string; ticker: string; color: string; bg: string }> = {
		BTCUSDT: { name: 'Bitcoin',  ticker: 'BTC / USDT', color: '#ea8c0e', bg: '#fff8ef' },
		ETHUSDT: { name: 'Ethereum', ticker: 'ETH / USDT', color: '#4f63d2', bg: '#f3f5ff' },
	};

	const fmt     = (n: number, d = 2) => n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
	const fmtTime = (iso: string)      => new Date(iso).toLocaleTimeString('en-GB', { hour12: false });

	function sessionChange(symbol: string, current: number): { pct: number; dir: 'up' | 'down' | 'flat' } {
		const hist = priceHistory[symbol];
		if (!hist || hist.length < 2) return { pct: 0, dir: 'flat' };
		const first = hist[0];
		const pct   = ((current - first) / first) * 100;
		return { pct: Math.abs(pct), dir: pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat' };
	}

	// Build an SVG polyline path from an array of prices.
	function sparkPath(values: number[], w: number, h: number, pad = 3): string {
		if (values.length < 2) return '';
		const min   = Math.min(...values);
		const max   = Math.max(...values);
		const range = max - min || 1;
		const pts   = values.map((v, i) => {
			const x = (i / (values.length - 1)) * w;
			const y = pad + (1 - (v - min) / range) * (h - pad * 2);
			return `${x.toFixed(2)},${y.toFixed(2)}`;
		});
		return 'M ' + pts.join(' L ');
	}

	function sparkArea(values: number[], w: number, h: number, pad = 3): string {
		if (values.length < 2) return '';
		return `${sparkPath(values, w, h, pad)} L ${w},${h} L 0,${h} Z`;
	}

	function lastPoint(values: number[], w: number, h: number, pad = 3): { x: number; y: number } {
		if (values.length < 1) return { x: 0, y: 0 };
		const min  = Math.min(...values);
		const max  = Math.max(...values);
		const range = max - min || 1;
		const last = values[values.length - 1];
		return {
			x: w,
			y: pad + (1 - (last - min) / range) * (h - pad * 2),
		};
	}

	async function refresh() {
		try {
			const res  = await fetch('/api/data');
			if (!res.ok) return;
			const data = await res.json();

			for (const p of data.prices as Price[]) {
				// Flash animation
				const prev = prevPrices[p.symbol];
				if (prev !== undefined && prev !== p.price) {
					const dir = p.price > prev ? 'up' : 'down';
					flashDir = { ...flashDir, [p.symbol]: dir };
					setTimeout(() => { flashDir = { ...flashDir, [p.symbol]: '' }; }, 700);
				}
				prevPrices[p.symbol] = p.price;

				// Accumulate price history
				const hist = priceHistory[p.symbol] ?? [];
				hist.push(p.price);
				if (hist.length > HISTORY_MAX) hist.shift();
				priceHistory = { ...priceHistory, [p.symbol]: hist };
			}

			prices    = data.prices;
			trades    = data.trades;
			connected = true;
		} catch {
			connected = false;
		}
	}

	onMount(() => {
		clock = new Date().toLocaleTimeString('en-GB', { hour12: false });
		refresh();
		interval = setInterval(() => {
			refresh();
			clock = new Date().toLocaleTimeString('en-GB', { hour12: false });
		}, 1500);
	});
	onDestroy(() => clearInterval(interval));
</script>

<div class="shell">

	<!-- ── Header ─────────────────────────────────────────── -->
	<header class="hdr">
		<div class="hdr-left">
			<span class="logo">Dataworld</span>
			<span class="logo-tag">Crypto Terminal</span>
		</div>
		<div class="pipeline">
			<span>Binance</span>
			<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6h8M7 3l3 3-3 3" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
			<span>Kafka</span>
			<svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6h8M7 3l3 3-3 3" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
			<span>DuckDB</span>
		</div>
		<div class="hdr-right">
			<span class="status-dot {connected ? 'live' : 'dead'}"></span>
			<span class="status-lbl">{connected ? 'Live' : 'Offline'}</span>
			<span class="clock">{clock}</span>
		</div>
	</header>

	<!-- ── Price Cards ────────────────────────────────────── -->
	<section class="cards">
		{#each prices as p (p.symbol)}
			{@const m    = META[p.symbol] ?? { name: p.symbol, ticker: p.symbol, color: '#334155', bg: '#f8fafc' }}
			{@const dir  = flashDir[p.symbol] ?? ''}
			{@const hist = priceHistory[p.symbol] ?? []}
			{@const chg  = sessionChange(p.symbol, p.price)}
			{@const W = 300; const H = 72}
			<div class="card" style="--accent:{m.color}; --bg:{m.bg}">

				<div class="card-top">
					<div class="card-identity">
						<span class="coin-dot" style="background:{m.color}"></span>
						<div>
							<div class="coin-name">{m.name}</div>
							<div class="coin-ticker">{m.ticker}</div>
						</div>
					</div>
					<div class="card-stat">
						<div class="stat-val">{p.total_trades.toLocaleString()}</div>
						<div class="stat-lbl">trades</div>
					</div>
				</div>

				<!-- Price + session change -->
				<div class="price-row">
					<div class="price {dir}">
						<span class="price-sym">$</span>{fmt(p.price)}
					</div>
					{#if chg.dir !== 'flat'}
						<span class="chg {chg.dir}">
							{chg.dir === 'up' ? '▲' : '▼'}&thinsp;{chg.pct.toFixed(3)}%
						</span>
					{/if}
				</div>

				<!-- Sparkline -->
				<div class="spark-wrap">
					{#if hist.length > 1}
						{@const tip = lastPoint(hist, W, H)}
						<svg
							viewBox="0 0 {W} {H}"
							preserveAspectRatio="none"
							class="spark"
							aria-hidden="true"
						>
							<defs>
								<linearGradient id="fill-{p.symbol}" x1="0" y1="0" x2="0" y2="1">
									<stop offset="0%"   stop-color="{m.color}" stop-opacity="0.18"/>
									<stop offset="100%" stop-color="{m.color}" stop-opacity="0.01"/>
								</linearGradient>
							</defs>
							<!-- Area fill -->
							<path d="{sparkArea(hist, W, H)}" fill="url(#fill-{p.symbol})"/>
							<!-- Line -->
							<path d="{sparkPath(hist, W, H)}" fill="none" stroke="{m.color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
							<!-- Latest price dot -->
							<circle cx="{tip.x}" cy="{tip.y}" r="3" fill="{m.color}"/>
							<circle cx="{tip.x}" cy="{tip.y}" r="5" fill="{m.color}" opacity="0.2"/>
						</svg>
					{:else}
						<div class="spark-empty">Collecting data…</div>
					{/if}
				</div>

				<div class="card-foot">
					<span>Vol&ensp;<strong>{fmt(p.total_volume, 4)}</strong></span>
					<span>Updated&ensp;<strong>{fmtTime(p.updated_at)}</strong></span>
				</div>
			</div>
		{:else}
			{#each [0, 1] as _}
				<div class="card card-empty" style="--accent:#e2e8f0; --bg:#f8fafc">
					<div class="price">Awaiting feed…</div>
				</div>
			{/each}
		{/each}
	</section>

	<!-- ── Trade Feed ─────────────────────────────────────── -->
	<section class="feed">
		<div class="feed-hdr">
			<span class="feed-title">Live Trades</span>
			<span class="feed-count">{trades.length} records</span>
		</div>
		<div class="tbl-wrap">
			<table class="tbl">
				<thead>
					<tr>
						<th>Time</th>
						<th>Pair</th>
						<th class="r">Price</th>
						<th class="r">Qty</th>
						<th class="r">Notional</th>
						<th class="c">Side</th>
					</tr>
				</thead>
				<tbody>
					{#each trades as t, i (t.trade_id)}
						{@const m = META[t.symbol]}
						<tr class:latest={i === 0}>
							<td class="dim">{fmtTime(t.trade_time)}</td>
							<td>
								<span class="pair-name" style="color:{m?.color ?? '#334155'}">{t.symbol.replace('USDT', '')}</span><span class="pair-quote">/USDT</span>
							</td>
							<td class="r mono">${fmt(t.price)}</td>
							<td class="r mono dim">{fmt(t.quantity, 5)}</td>
							<td class="r mono">${fmt(t.notional)}</td>
							<td class="c">
								<span class="badge {t.buyer_maker ? 'sell' : 'buy'}">{t.buyer_maker ? 'Sell' : 'Buy'}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>
</div>

<style>
	:global(body) { margin: 0; background: #f1f5f9; }

	.shell {
		min-height: 100vh;
		background: #f1f5f9;
		font-family: 'DM Sans', system-ui, sans-serif;
		font-size: 13px;
		color: #334155;
	}

	/* ── Header ── */
	.hdr {
		display: flex; align-items: center; justify-content: space-between;
		padding: 14px 28px;
		background: #ffffff;
		border-bottom: 1px solid #e2e8f0;
		box-shadow: 0 1px 3px rgba(0,0,0,.04);
	}
	.hdr-left { display: flex; align-items: baseline; gap: 10px; }
	.logo { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; color: #0f172a; letter-spacing: .04em; }
	.logo-tag { font-size: 11px; color: #94a3b8; letter-spacing: .05em; }
	.pipeline { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #94a3b8; }
	.hdr-right { display: flex; align-items: center; gap: 8px; font-size: 12px; }
	.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
	.status-dot.live  { background: #22c55e; box-shadow: 0 0 0 2px rgba(34,197,94,.2); animation: pulse-dot 2s ease-in-out infinite; }
	.status-dot.dead  { background: #ef4444; }
	@keyframes pulse-dot { 0%,100%{box-shadow:0 0 0 2px rgba(34,197,94,.2)} 50%{box-shadow:0 0 0 5px rgba(34,197,94,.08)} }
	.status-lbl { color: #22c55e; font-weight: 500; }
	.clock { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #94a3b8; padding-left: 10px; border-left: 1px solid #e2e8f0; }

	/* ── Cards ── */
	.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 24px 28px; }

	.card {
		background: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 14px;
		padding: 24px 26px 0;
		position: relative; overflow: hidden;
		box-shadow: 0 1px 4px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.03);
		transition: box-shadow .2s;
	}
	.card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.07), 0 8px 24px rgba(0,0,0,.06); }

	.card::before {
		content: '';
		position: absolute; top: 0; left: 0; right: 0;
		height: 3px; border-radius: 14px 14px 0 0;
		background: var(--accent);
	}
	.card::after {
		content: '';
		position: absolute; top: 0; right: 0;
		width: 180px; height: 140px;
		background: radial-gradient(ellipse at top right, var(--bg) 0%, transparent 70%);
		pointer-events: none;
	}

	.card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
	.card-identity { display: flex; align-items: center; gap: 12px; }
	.coin-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
	.coin-name  { font-size: 14px; font-weight: 600; color: #0f172a; }
	.coin-ticker { font-size: 11px; color: #94a3b8; margin-top: 1px; }
	.card-stat { text-align: right; }
	.stat-val { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: #334155; font-variant-numeric: tabular-nums; }
	.stat-lbl { font-size: 10px; color: #94a3b8; margin-top: 1px; }

	/* Price + change badge */
	.price-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }

	.price {
		font-family: 'Rajdhani', sans-serif;
		font-size: 52px; font-weight: 700; line-height: 1;
		color: #0f172a; letter-spacing: -.01em;
		font-variant-numeric: tabular-nums;
	}
	.price.up   { animation: fup   .7s ease-out forwards; }
	.price.down { animation: fdown .7s ease-out forwards; }
	@keyframes fup   { 0%{color:#16a34a} 100%{color:#0f172a} }
	@keyframes fdown { 0%{color:#dc2626} 100%{color:#0f172a} }
	.price-sym { font-size: 26px; color: #94a3b8; vertical-align: super; margin-right: 1px; }

	.chg {
		font-family: 'JetBrains Mono', monospace;
		font-size: 11px; font-weight: 500;
		padding: 2px 7px; border-radius: 20px;
	}
	.chg.up   { color: #16a34a; background: #f0fdf4; }
	.chg.down { color: #dc2626; background: #fef2f2; }

	/* Sparkline */
	.spark-wrap {
		margin: 0 -26px;
		height: 80px;
		display: flex; align-items: stretch;
	}

	.spark {
		width: 100%; height: 100%;
		display: block;
	}

	.spark-empty {
		width: 100%; display: flex; align-items: center; justify-content: center;
		font-size: 11px; color: #cbd5e1;
	}

	.card-foot {
		display: flex; gap: 18px;
		font-size: 11px; color: #94a3b8;
		padding: 12px 26px 18px;
		margin: 0 -26px;
		border-top: 1px solid #f1f5f9;
		margin-top: 0;
	}
	.card-foot strong { color: #475569; font-weight: 500; }

	.card-empty .price { font-size: 20px; color: #cbd5e1; }

	/* ── Feed ── */
	.feed { margin: 0 28px 28px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
	.feed-hdr { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; border-bottom: 1px solid #f1f5f9; }
	.feed-title { font-size: 13px; font-weight: 600; color: #0f172a; }
	.feed-count { font-size: 11px; color: #94a3b8; }

	.tbl-wrap { overflow-x: auto; overflow-y: auto; max-height: calc(100vh - 360px); }
	.tbl { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
	.tbl thead tr { position: sticky; top: 0; background: #ffffff; z-index: 2; }
	.tbl th { padding: 9px 18px; text-align: left; font-size: 10px; font-weight: 600; letter-spacing: .06em; color: #94a3b8; text-transform: uppercase; border-bottom: 1px solid #f1f5f9; }
	.tbl th.r { text-align: right; }
	.tbl th.c { text-align: center; }
	.tbl td { padding: 7px 18px; border-bottom: 1px solid #f8fafc; color: #334155; font-size: 12px; }
	.tbl td.r { text-align: right; }
	.tbl td.c { text-align: center; }
	.tbl td.dim { color: #94a3b8; }
	.tbl td.mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
	.tbl tr.latest td { background: #f8fafc; }
	.tbl tbody tr:hover td { background: #f8fafc; }

	.pair-name  { font-weight: 600; font-size: 13px; }
	.pair-quote { color: #94a3b8; font-size: 12px; }
	.badge { display: inline-block; padding: 2px 9px; font-size: 10px; font-weight: 600; border-radius: 20px; }
	.badge.buy  { color: #16a34a; background: #f0fdf4; }
	.badge.sell { color: #dc2626; background: #fef2f2; }
</style>
