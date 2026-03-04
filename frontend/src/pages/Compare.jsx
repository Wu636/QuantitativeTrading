import { useState } from 'react'
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    BarChart, Bar,
} from 'recharts'
import { BarChart2 } from 'lucide-react'

const API = ''

const ALL_STRATEGIES = [
    { key: 'dual_ma', label: '双均线' },
    { key: 'enhanced_dual_ma', label: '增强双均线' },
    { key: 'macd', label: 'MACD' },
    { key: 'bollinger', label: '布林带' },
    { key: 'multi_factor', label: '多因子' },
    { key: 'turtle', label: '海龟策略' },
]

const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#a78bfa', '#06b6d4']

function pct(v, signed = true) {
    if (v === undefined || v === null) return '—'
    const p = (v * 100).toFixed(2)
    return `${signed && p > 0 ? '+' : ''}${p}%`
}

export default function Compare() {
    const [symbol, setSymbol] = useState('000001')
    const [selected, setSelected] = useState(ALL_STRATEGIES.map(s => s.key))
    const [capital, setCapital] = useState('100000')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    function toggleStrategy(key) {
        setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
    }

    async function run() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const res = await fetch(`${API}/api/compare`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol.trim(),
                    strategy_names: selected,
                    initial_capital: parseFloat(capital),
                }),
            })
            if (!res.ok) throw new Error((await res.json()).detail || '请求失败')
            setResult(await res.json())
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    // Build chart data (merge daily from all strategies)
    let chartData = []
    if (result?.results?.length) {
        const baseDaily = result.results[0].daily
        const step = Math.ceil(baseDaily.length / 300)
        chartData = baseDaily
            .filter((_, i) => i % step === 0)
            .map(d => {
                const point = { date: d.date, benchmark: d.benchmark }
                result.results.forEach(r => {
                    const match = r.daily.find(x => x.date === d.date)
                    if (match) point[r.key] = match.net_value
                })
                return point
            })
    }

    // Bar chart data for metrics
    const barData = result?.results?.map(r => ({
        name: ALL_STRATEGIES.find(s => s.key === r.key)?.label || r.key,
        总收益: +(r.metrics.total_return * 100).toFixed(2),
        最大回撤: +(r.metrics.max_drawdown * 100).toFixed(2),
        夏普: +r.metrics.sharpe_ratio.toFixed(2),
    })) || []

    return (
        <div className="animate-fadein">
            <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>策略对比</h1>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 }}>
                同一标的，多策略并行回测对比
            </p>

            {/* Controls */}
            <div className="card" style={{ marginBottom: 24 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '160px 160px 1fr auto', gap: 16, alignItems: 'end' }}>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>股票代码</label>
                        <input className="input-field" placeholder="如 000001" value={symbol} onChange={e => setSymbol(e.target.value)} />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>初始资金</label>
                        <input className="input-field" type="number" value={capital} onChange={e => setCapital(e.target.value)} />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>选择策略</label>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {ALL_STRATEGIES.map(s => (
                                <button key={s.key} onClick={() => toggleStrategy(s.key)}
                                    style={{
                                        padding: '5px 12px', borderRadius: 6, fontSize: 13, cursor: 'pointer', border: 'none',
                                        background: selected.includes(s.key) ? 'var(--accent-blue)' : 'var(--bg-secondary)',
                                        color: selected.includes(s.key) ? 'white' : 'var(--text-secondary)',
                                        transition: 'all 0.15s',
                                    }}>
                                    {s.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    <button className="btn btn-primary" onClick={run} disabled={loading || selected.length === 0} style={{ height: 38 }}>
                        {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <BarChart2 size={15} />}
                        {loading ? '运行中…' : '对比'}
                    </button>
                </div>
            </div>

            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 8, padding: '12px 16px', marginBottom: 20, color: 'var(--accent-red)', fontSize: 14
                }}>
                    ❌ {error}
                </div>
            )}

            {loading && (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
                    <div className="spinner" style={{ width: 36, height: 36, margin: '0 auto 16px' }} />
                    <div>正在对比 {selected.length} 个策略，请稍候…</div>
                </div>
            )}

            {result && !loading && (
                <>
                    <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 18, fontWeight: 700 }}>{result.stock_name}</span>
                        <span className="tag tag-blue">{result.symbol}</span>
                        <span className="tag tag-gold">基准: {pct(result.benchmark_return)}</span>
                    </div>

                    {/* Metrics Table */}
                    <div className="card" style={{ marginBottom: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>对比总览</div>
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>策略</th>
                                        <th>总收益</th><th>年化收益</th><th>最大回撤</th>
                                        <th>夏普比率</th><th>胜率</th><th>盈亏比</th><th>交易次数</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {result.results.map((r, i) => {
                                        const m = r.metrics
                                        const beat = m.total_return > result.benchmark_return
                                        return (
                                            <tr key={r.key}>
                                                <td>
                                                    <span style={{ color: COLORS[i % COLORS.length], fontWeight: 600 }}>●</span>{'  '}
                                                    {ALL_STRATEGIES.find(s => s.key === r.key)?.label}
                                                    {beat && <span className="tag tag-green" style={{ marginLeft: 6 }}>超基准</span>}
                                                </td>
                                                <td style={{ color: m.total_return > 0 ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 600 }}>
                                                    {pct(m.total_return)}
                                                </td>
                                                <td style={{ color: m.annual_return > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                                                    {pct(m.annual_return)}
                                                </td>
                                                <td style={{ color: 'var(--accent-red)' }}>{pct(m.max_drawdown, false)}</td>
                                                <td style={{ color: m.sharpe_ratio > 1 ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
                                                    {m.sharpe_ratio?.toFixed(2)}
                                                </td>
                                                <td>{pct(m.win_rate, false)}</td>
                                                <td>{m.profit_loss_ratio?.toFixed(2)}</td>
                                                <td style={{ color: 'var(--text-secondary)' }}>{m.total_trades}</td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Net Value Chart */}
                    <div className="card" style={{ marginBottom: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>净值走势对比</div>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                <XAxis dataKey="date" tick={{ fill: '#8fa3c4', fontSize: 11 }} tickFormatter={v => v.slice(0, 7)} interval="preserveStartEnd" />
                                <YAxis tick={{ fill: '#8fa3c4', fontSize: 11 }} domain={['auto', 'auto']} />
                                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }}
                                    formatter={(v) => v.toFixed(4)} />
                                <Legend />
                                <Line type="monotone" dataKey="benchmark" stroke="#6b7280" dot={false} strokeWidth={1.5}
                                    strokeDasharray="4 2" name="基准" />
                                {result.results.map((r, i) => (
                                    <Line key={r.key} type="monotone" dataKey={r.key} stroke={COLORS[i % COLORS.length]}
                                        dot={false} strokeWidth={2}
                                        name={ALL_STRATEGIES.find(s => s.key === r.key)?.label} />
                                ))}
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Bar Chart */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                        <div className="card">
                            <div style={{ fontWeight: 600, marginBottom: 16 }}>总收益 & 夏普比率</div>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={barData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                    <XAxis dataKey="name" tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                                    <Bar dataKey="总收益" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="夏普" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="card">
                            <div style={{ fontWeight: 600, marginBottom: 16 }}>最大回撤（%）</div>
                            <ResponsiveContainer width="100%" height={200}>
                                <BarChart data={barData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                    <XAxis dataKey="name" tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                    <YAxis tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                                    <Bar dataKey="最大回撤" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
