import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Avatar, Badge, Button, Card, FluentProvider, Tab, TabList, Tooltip, webDarkTheme } from '@fluentui/react-components';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD'];
const money = (value) => Number.isFinite(value) ? value.toFixed(5) : '—';
const percent = (value) => Number.isFinite(value) ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%` : '—';

async function request(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.detail || `API request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function Chart({ bars }) {
  if (!bars?.length) return <div className="chart-empty">No market history yet. Sync daily data to populate this chart.</div>;
  const width = 1000, height = 270, pad = { top: 18, right: 12, bottom: 22, left: 12 };
  const min = Math.min(...bars.map((b) => b.low)), max = Math.max(...bars.map((b) => b.high));
  const span = max - min || 1;
  const y = (v) => pad.top + (max - v) / span * (height - pad.top - pad.bottom);
  const step = (width - pad.left - pad.right) / bars.length;
  const bodyWidth = Math.max(2, Math.min(10, step * .55));
  return <div className="chart-shell"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${bars.length} daily ${bars[0] ? 'OHLC' : ''} candles`} preserveAspectRatio="none">
    {[0, .25, .5, .75, 1].map((fraction) => <line key={fraction} x1="0" x2={width} y1={pad.top + fraction * (height - pad.top - pad.bottom)} y2={pad.top + fraction * (height - pad.top - pad.bottom)} className="chart-grid-line"/>)}
    {bars.map((bar, index) => { const x = pad.left + (index + .5) * step; const up = bar.close >= bar.open; const top = y(Math.max(bar.open, bar.close)); const bottom = y(Math.min(bar.open, bar.close)); return <g key={bar.timestamp} className={up ? 'chart-up' : 'chart-down'}><line x1={x} x2={x} y1={y(bar.high)} y2={y(bar.low)} stroke="currentColor"/><rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={Math.max(1, bottom - top)} fill="currentColor"/></g>; })}
  </svg><div className="chart-dates"><span>{new Date(bars[0].timestamp).toLocaleDateString()}</span><span>{new Date(bars[bars.length - 1].timestamp).toLocaleDateString()}</span></div></div>;
}

function App() {
  const [pair, setPair] = useState(pairs[0]);
  const [market, setMarket] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError('');
    const [marketResult, predictionResult, modelResult] = await Promise.allSettled([
      request(`/market/${pair.replace('/', '')}?timeframe=1d&limit=250`),
      request(`/predictions/${pair.replace('/', '')}?timeframe=1d`),
      request(`/models/${pair.replace('/', '')}?timeframe=1d`),
    ]);
    setMarket(marketResult.status === 'fulfilled' ? marketResult.value : null);
    setPrediction(predictionResult.status === 'fulfilled' ? predictionResult.value : null);
    setModel(modelResult.status === 'fulfilled' ? modelResult.value : null);
    const failures = [marketResult, predictionResult, modelResult].filter((r) => r.status === 'rejected');
    if (failures.length === 3) setError(`API unavailable: ${failures[0].reason.message}`);
    else if (marketResult.status === 'rejected') setError(`Market data unavailable: ${marketResult.reason.message}`);
    else if (predictionResult.status === 'rejected' && predictionResult.reason.status !== 404) setError(`Forecast unavailable: ${predictionResult.reason.message}`);
    else if (modelResult.status === 'rejected' && modelResult.reason.status !== 404) setError(`Model metadata unavailable: ${modelResult.reason.message}`);
    setLoading(false);
    setRefreshing(false);
  }, [pair]);

  useEffect(() => { setLoading(true); setMarket(null); setPrediction(null); setModel(null); refresh(); }, [refresh]);
  const bars = market?.bars || [];
  const latest = bars.at(-1);
  const prior = bars.at(-2);
  const change = latest && prior ? latest.close / prior.close - 1 : null;
  const probabilities = prediction?.next_state_probabilities || {};

  return <FluentProvider theme={webDarkTheme} className="app-theme"><div className="app-frame">
    <header className="app-header"><a className="wordmark" href="#terminal">markov<span>fx</span></a><nav aria-label="Primary"><a className="nav-current" href="#terminal">Terminal</a><a href="#method">Method</a><a href="#operations">Operations</a></nav><div className="header-actions"><Badge appearance="tint" color={market?.stale ? 'warning' : 'informative'}>{market?.stale ? 'Data stale' : market ? 'Daily data' : 'Connecting'}</Badge><Tooltip content="Account settings" relationship="label"><Avatar name="FX" size={28}/></Tooltip></div></header>
    <main id="terminal" className="terminal-layout"><aside className="watchlist"><div className="section-kicker">Watchlist</div><div className="pair-list">{pairs.map((item) => <button key={item} className={`pair-row ${pair === item ? 'pair-selected' : ''}`} onClick={() => setPair(item)}><span><b>{item}</b><small>{item.replace('/', '')}=X</small></span><span><strong>{pair === item && latest ? money(latest.close) : '—'}</strong><em className={change >= 0 ? 'up' : 'down'}>{pair === item ? percent(change) : '—'}</em></span></button>)}</div><div className="watchlist-footer"><span className="section-kicker">Approved model</span><b>{model?.model_version || 'Unavailable'}</b><small>{model ? `${model.feature_version} · ${model.status}` : 'No approved model for this pair'}</small></div></aside>
      <section className="content-area"><div className="page-intro"><div><span className="section-kicker">Forecasting workspace</span><h1>Read the regime, not the noise.</h1><p>Daily market states from validated OHLC history and an approved Hidden Markov Model.</p></div><Button appearance="primary" onClick={refresh} disabled={refreshing}>{refreshing ? 'Refreshing…' : 'Refresh data'}</Button></div>
        <div className={`notice ${error ? 'notice-error' : ''}`} role="status">{loading ? 'Connecting to the forecast API…' : error || (market?.stale ? 'Market history is stale. Check the latest data sync.' : `Updated from API${market?.as_of_timestamp ? ` · as of ${new Date(market.as_of_timestamp).toLocaleDateString()}` : ''}`)}</div>
        <section className="market-panel"><div className="market-bar"><div><div className="pair-title"><h2>{pair}</h2><Badge appearance="outline">1D</Badge></div><div className="spot-price">{money(latest?.close)} <span className={change >= 0 ? 'up' : 'down'}>{percent(change)}</span></div><p>{bars.length ? `${bars.length} daily bars · source and timestamps provided by the API` : 'Waiting for persisted daily OHLC data'}</p></div><TabList selectedValue="1D" size="small"><Tab value="1D">1D</Tab></TabList></div><Chart bars={bars}/></section>
        <div className="analysis-grid"><Card className="signal-card"><span className="section-kicker">Latest forecast · {prediction?.forecast_horizon || '—'}</span><div className="signal-line"><div><strong className={prediction?.signal === 'SELL' ? 'down' : ''}>{prediction?.signal || '—'}</strong><span>{prediction?.current_regime ? `Current regime · ${prediction.current_regime}` : 'No approved model forecast'}</span></div><Badge color={prediction?.signal === 'BUY' ? 'success' : prediction ? 'warning' : 'informative'} appearance="tint">{prediction?.forecast_for_timestamp ? `For ${new Date(prediction.forecast_for_timestamp).toLocaleDateString()}` : 'Not available'}</Badge></div><p>{prediction ? `Current-state posterior and next-state transition probabilities are returned separately by ${prediction.model_version}.` : 'An approved model is required before the API can return a forecast.'}</p><div className="confidence-row"><span>Current state</span><b>{prediction ? `${(Math.max(...Object.values(prediction.current_probabilities)) * 100).toFixed(0)}%` : '—'}</b><span>Posterior probability</span></div></Card>
          <Card className="regime-card"><span className="section-kicker">Next-state probabilities</span><h2>{prediction ? `From ${prediction.current_regime}` : 'Waiting for approved model'}</h2><div className="probability-list">{['Bull', 'Sideways', 'Bear'].map((regime) => <div key={regime}><span>{regime}</span><b>{probabilities[regime] == null ? '—' : `${(probabilities[regime] * 100).toFixed(1)}%`}</b><i style={{ background: `linear-gradient(90deg, ${regime === 'Bull' ? '#71c99b' : regime === 'Bear' ? '#d68a7e' : '#b7aa7a'} ${((probabilities[regime] || 0) * 100).toFixed(1)}%, #29372f ${((probabilities[regime] || 0) * 100).toFixed(1)}%)` }}/></div>)}</div><p>Transition probabilities are distinct from the current-state posterior.</p></Card></div>
        <section id="operations" className="operations"><div><span className="section-kicker">Data lineage</span><h2>Every forecast has a route back to its source.</h2></div><div className="lineage"><div><b>Yahoo Finance</b><span>daily OHLC ingestion</span></div><i>→</i><div><b>SQL database</b><span>validated, idempotent bars</span></div><i>→</i><div><b>Approved HMM</b><span>{model?.model_version || 'No model selected'}</span></div><i>→</i><div><b>FastAPI</b><span>versioned prediction contract</span></div></div><div className="run-note"><Badge color={market?.stale ? 'warning' : 'success'} appearance="tint">{market ? market.stale ? 'Sync needed' : 'API connected' : 'No data'}</Badge><span>{market ? `${bars.length} bars returned. Model status: ${model?.status || 'no approved model'}.` : 'Start the API and sync EUR/USD daily data to begin.'}</span></div></section>
        <section id="method" className="method"><div><span className="section-kicker">Method</span><h2>Small, explainable inputs.</h2><p>Log return, intrabar return, daily range, and rolling 20-period volatility are standardized using training-window statistics.</p></div><div className="method-metrics"><div><b>3</b><span>market states</span></div><div><b>20</b><span>volatility window</span></div><div><b>{model?.feature_version || 'v1'}</b><span>feature version</span></div></div></section>
      </section></main><footer>Probabilistic analysis only; no orders are placed. <span>Market data via backend yfinance ingestion</span></footer>
  </div></FluentProvider>;
}

createRoot(document.getElementById('root')).render(<App/>);
