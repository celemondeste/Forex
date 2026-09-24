import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Avatar, Badge, Button, Card, FluentProvider, Input, Spinner, Tab, TabList, Tooltip, webDarkTheme } from '@fluentui/react-components';
import './styles.css';

const API = import.meta.env.VITE_API_URL || '/api';
const defaultPairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD'];
const HORIZON = 30;
const symbolOf = (pair) => pair.replace('/', '');
const money = (value) => Number.isFinite(value) ? value.toFixed(value >= 100 ? 3 : 5) : '—';
const percent = (value) => Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%` : '—';
const shortDate = (value) => new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

async function request(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail || `API request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function Chart({ bars }) {
  if (!bars?.length) return <div className="chart-empty">No market history yet. Search a currency pair to ingest its daily history.</div>;
  const width = 1000, height = 270, pad = { top: 18, right: 12, bottom: 22, left: 12 };
  const min = Math.min(...bars.map((b) => b.low)), max = Math.max(...bars.map((b) => b.high));
  const span = max - min || 1;
  const y = (v) => pad.top + (max - v) / span * (height - pad.top - pad.bottom);
  const step = (width - pad.left - pad.right) / bars.length;
  const bodyWidth = Math.max(2, Math.min(10, step * .55));
  return <div className="chart-shell"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${bars.length} daily OHLC candles`} preserveAspectRatio="none">
    {[0, .25, .5, .75, 1].map((fraction) => <line key={fraction} x1="0" x2={width} y1={pad.top + fraction * (height - pad.top - pad.bottom)} y2={pad.top + fraction * (height - pad.top - pad.bottom)} className="chart-grid-line"/>)}
    {bars.map((bar, index) => { const x = pad.left + (index + .5) * step; const up = bar.close >= bar.open; const top = y(Math.max(bar.open, bar.close)); const bottom = y(Math.min(bar.open, bar.close)); return <g key={bar.timestamp} className={up ? 'chart-up' : 'chart-down'}><line x1={x} x2={x} y1={y(bar.high)} y2={y(bar.low)} stroke="currentColor"/><rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={Math.max(1, bottom - top)} fill="currentColor"/></g>; })}
  </svg><div className="chart-dates"><span>{new Date(bars[0].timestamp).toLocaleDateString()}</span><span>{new Date(bars[bars.length - 1].timestamp).toLocaleDateString()}</span></div></div>;
}

function ForecastChart({ bars, forecast }) {
  if (!forecast?.points?.length) {
    return <div className="chart-empty">No forecast yet. An approved Hidden Markov Model is required for this pair.</div>;
  }
  const history = bars.slice(-90).map((bar) => ({ timestamp: bar.timestamp, close: bar.close }));
  const points = forecast.points;
  const width = 1000, height = 270, pad = { top: 18, right: 14, bottom: 24, left: 14 };
  const lows = [...history.map((b) => b.close), ...points.map((p) => p.lower)];
  const highs = [...history.map((b) => b.close), ...points.map((p) => p.upper)];
  const min = Math.min(...lows), max = Math.max(...highs);
  const span = max - min || 1;
  const total = history.length + points.length;
  const x = (index) => pad.left + index * (width - pad.left - pad.right) / Math.max(1, total - 1);
  const y = (value) => pad.top + (max - value) / span * (height - pad.top - pad.bottom);
  const historyLine = history.map((bar, index) => `${index ? 'L' : 'M'}${x(index)} ${y(bar.close)}`).join(' ');
  const anchor = history.length - 1;
  const expectedLine = [`M${x(anchor)} ${y(history.at(-1).close)}`,
    ...points.map((point, index) => `L${x(anchor + 1 + index)} ${y(point.expected)}`)].join(' ');
  const band = [`M${x(anchor)} ${y(history.at(-1).close)}`,
    ...points.map((point, index) => `L${x(anchor + 1 + index)} ${y(point.upper)}`),
    ...points.slice().reverse().map((point, index) => `L${x(total - 1 - index)} ${y(point.lower)}`),
    'Z'].join(' ');
  const last = points.at(-1);

  return <div className="chart-shell">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" preserveAspectRatio="none"
         aria-label={`Simulated ${forecast.horizon_days}-session price forecast with a 10th to 90th percentile band`}>
      {[0, .25, .5, .75, 1].map((fraction) => <line key={fraction} x1="0" x2={width} className="chart-grid-line"
        y1={pad.top + fraction * (height - pad.top - pad.bottom)} y2={pad.top + fraction * (height - pad.top - pad.bottom)}/>)}
      <path d={band} className="forecast-band"/>
      <path d={historyLine} className="forecast-history"/>
      <path d={expectedLine} className="forecast-expected"/>
      <line x1={x(anchor)} x2={x(anchor)} y1={pad.top} y2={height - pad.bottom} className="forecast-divider"/>
      <circle cx={x(total - 1)} cy={y(last.expected)} r="3.5" className="forecast-endpoint"/>
    </svg>
    <div className="chart-dates">
      <span>{shortDate(history[0].timestamp)}</span>
      <span className="forecast-legend"><i className="swatch-history"/>history<i className="swatch-expected"/>median path<i className="swatch-band"/>10–90%</span>
      <span>{shortDate(last.timestamp)}</span>
    </div>
  </div>;
}

function PairSearch({ value, onSelect, busy }) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      request(`/currencies?q=${encodeURIComponent(query)}`, controller.signal)
        .then(setOptions)
        .catch(() => {});
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query]);

  useEffect(() => {
    const close = (event) => { if (box.current && !box.current.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const choose = (pair) => { setOpen(false); setQuery(''); onSelect(pair); };
  const submit = (event) => {
    event.preventDefault();
    const typed = query.trim().toUpperCase().replace(/[^A-Z]/g, '');
    if (typed.length === 6) return choose(`${typed.slice(0, 3)}/${typed.slice(3)}`);
    if (options[0]) return choose(options[0].pair);
  };

  return <form className="pair-search" onSubmit={submit} ref={box} role="search">
    <Input appearance="filled-darker" value={query} placeholder="Search a currency: EURUSD, JPY, vnd…"
      aria-label="Search a currency pair" onFocus={() => setOpen(true)}
      onChange={(_, data) => { setQuery(data.value); setOpen(true); }}/>
    <Button type="submit" appearance="primary" disabled={busy}>{busy ? 'Loading…' : 'Analyse'}</Button>
    {open && options.length > 0 && <ul className="search-results">
      {options.map((option) => <li key={option.pair}>
        <button type="button" className={option.pair === value ? 'result-current' : undefined} onClick={() => choose(option.pair)}>
          <b>{option.pair}</b><small>{option.label}</small><em>{option.symbol}=X</em>
        </button>
      </li>)}
    </ul>}
  </form>;
}

function App() {
  const [pair, setPair] = useState(defaultPairs[0]);
  const [watchlist, setWatchlist] = useState(defaultPairs);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setRefreshing(true);
    setError('');
    try {
      setData(await request(`/search/${symbolOf(pair)}?timeframe=1d&limit=250&horizon=${HORIZON}`));
    } catch (exception) {
      setData(null);
      setError(exception.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [pair]);

  useEffect(() => { setLoading(true); setData(null); load(); }, [load]);

  const select = (next) => {
    setPair(next);
    setWatchlist((current) => current.includes(next) ? current : [next, ...current].slice(0, 8));
  };

  const bars = data?.bars || [];
  const latest = bars.at(-1);
  const prior = bars.at(-2);
  const change = latest && prior ? latest.close / prior.close - 1 : null;
  const prediction = data?.prediction || null;
  const forecast = data?.forecast || null;
  const model = data?.model || null;
  const probabilities = prediction?.next_state_probabilities || {};
  const status = useMemo(() => {
    if (loading) return `Ingesting daily history and fitting the Hidden Markov Model for ${pair}…`;
    if (error) return error;
    if (data?.prepared_steps?.length) return `Prepared ${pair}: ${data.prepared_steps.join(' and ')} on demand.`;
    if (data?.stale) return 'Market history is stale. Refresh to sync the latest sessions.';
    return `Updated from API${data?.as_of_timestamp ? ` · as of ${new Date(data.as_of_timestamp).toLocaleDateString()}` : ''}`;
  }, [loading, error, data, pair]);

  return <FluentProvider theme={webDarkTheme} className="app-theme"><div className="app-frame">
    <header className="app-header"><a className="wordmark" href="#terminal">markov<span>fx</span></a><nav aria-label="Primary"><a className="nav-current" href="#terminal">Terminal</a><a href="#method">Method</a><a href="#operations">Operations</a></nav><div className="header-actions"><Badge appearance="tint" color={data?.stale ? 'warning' : 'informative'}>{data?.stale ? 'Data stale' : data ? 'Daily data' : 'Connecting'}</Badge><Tooltip content="Account settings" relationship="label"><Avatar name="FX" size={28}/></Tooltip></div></header>
    <main id="terminal" className="terminal-layout"><aside className="watchlist"><div className="section-kicker">Watchlist</div><div className="pair-list">{watchlist.map((item) => <button key={item} className={`pair-row ${pair === item ? 'pair-selected' : ''}`} onClick={() => select(item)}><span><b>{item}</b><small>{symbolOf(item)}=X</small></span><span><strong>{pair === item && latest ? money(latest.close) : '—'}</strong><em className={change >= 0 ? 'up' : 'down'}>{pair === item ? percent(change) : '—'}</em></span></button>)}</div><div className="watchlist-footer"><span className="section-kicker">Approved model</span><b>{model?.model_version || 'Unavailable'}</b><small>{model ? `${model.feature_version} · ${model.status}${model.metrics?.auto_approved ? ' (auto)' : ''}` : 'No approved model for this pair'}</small></div></aside>
      <section className="content-area"><div className="page-intro"><div><span className="section-kicker">Forecasting workspace</span><h1>Read the regime, not the noise.</h1><p>Search any currency pair: the API ingests its daily history, fits a Hidden Markov Model, and simulates the next {HORIZON} sessions.</p></div><Button appearance="primary" onClick={load} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh data'}</Button></div>
        <PairSearch value={pair} onSelect={select} busy={refreshing}/>
        <div className={`notice ${error ? 'notice-error' : ''}`} role="status">{loading ? <span className="notice-loading"><Spinner size="extra-tiny"/>{status}</span> : status}</div>
        <section className="market-panel"><div className="market-bar"><div><div className="pair-title"><h2>{pair}</h2><Badge appearance="outline">1D</Badge></div><div className="spot-price">{money(latest?.close)} <span className={change >= 0 ? 'up' : 'down'}>{percent(change)}</span></div><p>{bars.length ? `${bars.length} daily bars · source and timestamps provided by the API` : 'Waiting for persisted daily OHLC data'}</p></div><TabList selectedValue="1D" size="small"><Tab value="1D">1D</Tab></TabList></div><Chart bars={bars}/></section>
        <section className="market-panel"><div className="market-bar"><div><div className="pair-title"><h2>Forecast path</h2><Badge appearance="outline">{forecast ? `${forecast.horizon_days} sessions` : 'HMM'}</Badge></div><div className="spot-price">{forecast ? money(forecast.points.at(-1).expected) : '—'} <span className={forecast?.expected_return >= 0 ? 'up' : 'down'}>{percent(forecast?.expected_return)}</span></div><p>{forecast ? `${forecast.simulations} Monte Carlo regime paths sampled from ${forecast.model_version}` : 'Waiting for an approved model to simulate future sessions'}</p></div></div><ForecastChart bars={bars} forecast={forecast}/></section>
        <div className="analysis-grid"><Card className="signal-card"><span className="section-kicker">Latest forecast · {prediction?.forecast_horizon || '—'}</span><div className="signal-line"><div><strong className={prediction?.signal === 'SELL' ? 'down' : ''}>{prediction?.signal || '—'}</strong><span>{prediction?.current_regime ? `Current regime · ${prediction.current_regime}` : 'No approved model forecast'}</span></div><Badge color={prediction?.signal === 'BUY' ? 'success' : prediction ? 'warning' : 'informative'} appearance="tint">{prediction?.forecast_for_timestamp ? `For ${new Date(prediction.forecast_for_timestamp).toLocaleDateString()}` : 'Not available'}</Badge></div><p>{prediction ? `Current-state posterior and next-state transition probabilities are returned separately by ${prediction.model_version}.` : 'An approved model is required before the API can return a forecast.'}</p><div className="confidence-row"><span>Current state</span><b>{prediction ? `${(Math.max(...Object.values(prediction.current_probabilities)) * 100).toFixed(0)}%` : '—'}</b><span>Posterior probability</span></div></Card>
          <Card className="regime-card"><span className="section-kicker">Next-state probabilities</span><h2>{prediction ? `From ${prediction.current_regime}` : 'Waiting for approved model'}</h2><div className="probability-list">{['Bull', 'Sideways', 'Bear'].map((regime) => <div key={regime}><span>{regime}</span><b>{probabilities[regime] == null ? '—' : `${(probabilities[regime] * 100).toFixed(1)}%`}</b><i style={{ background: `linear-gradient(90deg, ${regime === 'Bull' ? '#71c99b' : regime === 'Bear' ? '#d68a7e' : '#b7aa7a'} ${((probabilities[regime] || 0) * 100).toFixed(1)}%, #29372f ${((probabilities[regime] || 0) * 100).toFixed(1)}%)` }}/></div>)}</div><p>Transition probabilities are distinct from the current-state posterior.</p></Card></div>
        <section id="operations" className="operations"><div><span className="section-kicker">Data lineage</span><h2>Every forecast has a route back to its source.</h2></div><div className="lineage"><div><b>Yahoo Finance</b><span>daily OHLC ingestion</span></div><i>→</i><div><b>SQL database</b><span>validated, idempotent bars</span></div><i>→</i><div><b>Approved HMM</b><span>{model?.model_version || 'No model selected'}</span></div><i>→</i><div><b>FastAPI</b><span>versioned prediction contract</span></div></div><div className="run-note"><Badge color={data?.stale ? 'warning' : 'success'} appearance="tint">{data ? data.stale ? 'Sync needed' : 'API connected' : 'No data'}</Badge><span>{data ? `${bars.length} bars returned. Model status: ${model?.status || 'no approved model'}.` : 'Search a pair to ingest its daily history.'}</span></div></section>
        <section id="method" className="method"><div><span className="section-kicker">Method</span><h2>Small, explainable inputs.</h2><p>Log return, intrabar return, daily range, and rolling 20-period volatility are standardized using training-window statistics. The forecast path resamples regimes through the transition matrix and draws log returns from each regime's fitted Gaussian.</p></div><div className="method-metrics"><div><b>3</b><span>market states</span></div><div><b>20</b><span>volatility window</span></div><div><b>{forecast?.simulations || 600}</b><span>simulated paths</span></div><div><b>{model?.feature_version || 'v1'}</b><span>feature version</span></div></div></section>
      </section></main><footer>Probabilistic analysis only; no orders are placed. <span>Market data via backend yfinance ingestion</span></footer>
  </div></FluentProvider>;
}

createRoot(document.getElementById('root')).render(<App/>);
