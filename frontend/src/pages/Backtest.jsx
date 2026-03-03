import { useState } from 'react'
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react'

const API = ''

const STRATEGIES = [
    { key: 'dual_ma', label: '双均线', params: { short_window: 5, long_window: 20 } },
    { key: 'enhanced_dual_ma', label: '增强双均线', params: { short_window: 10, long_window: 30, trend_window: 60 } },
    { key: 'macd', label: 'MACD', params: { fast_period: 12, slow_period: 26, signal_period: 9 } },
    { key: 'bollinger', label: '布林带', params: { bb_period: 20, bb_std: 2.0 } },
    { key: 'multi_factor', label: '多因子', params: { min_factors: 4 } },
    { key: 'turtle', label: '海龟策略', params: { entry_window: 20, exit_window: 10, atr_period: 20 } },
]

function MetricCard({ label, value, sub, up }) {
    const color = up === undefined ? 'var(--text-primary)' : up ? 'var(--accent-green)' : 'var(--accent-red)'
    return (
        <div className="card" style={{ padding: '16px 20px' }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
            {sub && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{sub}</div>}
        </div>
    )
}

function pct(v) {
    if (v === undefined || v === null) return '—'
    const p = (v * 100).toFixed(2)
    return `${p > 0 ? '+' : ''}${p}%`
}

export default function Backtest() {
    const [symbol, setSymbol] = useState('000001')
    const [strategyKey, setStrategyKey] = useState('dual_ma')
    const [capital, setCapital] = useState('100000')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const strategy = STRATEGIES.find(s => s.key === strategyKey)

    async function run() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const res = await fetch(`${API}/api/backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol.trim(),
                    strategy_name: strategyKey,
                    params: strategy.params,
                    initial_capital: parseFloat(capital),
                }),
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || '请求失败')
            }
            setResult(await res.json())
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    const m = result?.metrics

    // Down-sample daily data for performance
    const chartData = result?.daily
        ? result.daily.filter((_, i) => i % Math.ceil(result.daily.length / 300) === 0)
        : []

    return (
        <div className="animate-fadein">
            <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>单股回测</h1>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 }}>
                选择股票和策略，运行历史回测
            </p>

            {/* Controls */}
            <div className="card" style={{ marginBottom: 24 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 16, alignItems: 'end' }}>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            股票代码
                        </label>
                        <input
                            className="input-field"
                            placeholder="如 000001"
                            value={symbol}
                            onChange={e => setSymbol(e.target.value)}
                        />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            策略选择
                        </label>
                        <select className="select-field" value={strategyKey} onChange={e => setStrategyKey(e.target.value)}>
                            {STRATEGIES.map(s => (
                                <option key={s.key} value={s.key}>{s.label}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            初始资金（元）
                        </label>
                        <input
                            className="input-field"
                            type="number"
                            value={capital}
                            onChange={e => setCapital(e.target.value)}
                        />
                    </div>
                    <button className="btn btn-primary" onClick={run} disabled={loading} style={{ height: 38 }}>
                        {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <TrendingUp size={15} />}
                        {loading ? '运行中…' : '运行回测'}
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
                    <div>正在获取数据并运行回测，请稍候…</div>
                </div>
            )}

            {result && !loading && (
                <>
                    {/* Stock Name Banner */}
                    <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 20, fontWeight: 700 }}>{result.stock_name}</span>
                        <span className="tag tag-blue">{result.symbol}</span>
                        <span className="tag tag-gold" style={{ fontSize: 12 }}>{result.strategy}</span>
                    </div>

                    {/* Metrics */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                        <MetricCard
                            label="总收益率"
                            value={pct(m.total_return)}
                            sub={`年化 ${pct(m.annual_return)}`}
                            up={m.total_return > 0}
                        />
                        <MetricCard
                            label="超额收益"
                            value={pct(m.excess_return)}
                            sub={`基准 ${pct(m.benchmark_return)}`}
                            up={m.excess_return > 0}
                        />
                        <MetricCard
                            label="最大回撤"
                            value={pct(m.max_drawdown)}
                            up={false}
                        />
                        <MetricCard
                            label="夏普比率"
                            value={m.sharpe_ratio?.toFixed(2)}
                            up={m.sharpe_ratio > 1}
                        />
                        <MetricCard
                            label="胜率"
                            value={pct(m.win_rate)}
                            sub={`共 ${m.total_trades} 笔交易`}
                            up={m.win_rate > 0.5}
                        />
                        <MetricCard
                            label="盈亏比"
                            value={m.profit_loss_ratio?.toFixed(2)}
                            up={m.profit_loss_ratio > 1}
                        />
                        <MetricCard
                            label="最终资产"
                            value={`¥${m.final_value?.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`}
                            sub={`初始 ¥${m.initial_capital?.toLocaleString()}`}
                            up={m.final_value > m.initial_capital}
                        />
                        <MetricCard
                            label="总手续费"
                            value={`¥${m.total_commission?.toFixed(0)}`}
                            up={undefined}
                        />
                    </div>

                    {/* Chart */}
                    <div className="card" style={{ marginBottom: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>净值走势</div>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                <XAxis dataKey="date" tick={{ fill: '#8fa3c4', fontSize: 11 }}
                                    tickFormatter={v => v.slice(0, 7)} interval="preserveStartEnd" />
                                <YAxis tick={{ fill: '#8fa3c4', fontSize: 11 }} domain={['auto', 'auto']} />
                                <Tooltip
                                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }}
                                    labelStyle={{ color: 'var(--text-secondary)' }}
                                    formatter={(v, n) => [v.toFixed(4), n === 'net_value' ? '策略净值' : '基准净值']}
                                />
                                <Legend formatter={v => v === 'net_value' ? '策略净值' : '基准净值'} />
                                <Line type="monotone" dataKey="net_value" stroke="#3b82f6" dot={false} strokeWidth={2} />
                                <Line type="monotone" dataKey="benchmark" stroke="#6b7280" dot={false} strokeWidth={1.5} strokeDasharray="4 2" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Trade Records */}
                    <div className="card">
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>
                            交易明细 <span style={{ color: 'var(--text-secondary)', fontSize: 13, fontWeight: 400 }}>
                                ({result.trades.length} 条)
                            </span>
                        </div>
                        <div style={{ overflowX: 'auto', maxHeight: 320, overflowY: 'auto' }}>
                            <table className="data-table">
                                <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                                    <tr>
                                        <th>日期</th><th>方向</th><th>价格</th><th>数量</th><th>金额</th><th>手续费</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {result.trades.map((t, i) => (
                                        <tr key={i}>
                                            <td style={{ color: 'var(--text-secondary)' }}>{t.date}</td>
                                            <td>
                                                <span className={`tag ${t.action === 'buy' ? 'tag-green' : 'tag-red'}`}>
                                                    {t.action === 'buy' ? '买入' : '卖出'}
                                                </span>
                                            </td>
                                            <td>¥{t.price.toFixed(2)}</td>
                                            <td>{t.shares.toLocaleString()}</td>
                                            <td>¥{t.amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</td>
                                            <td style={{ color: 'var(--text-secondary)' }}>¥{t.commission.toFixed(2)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
