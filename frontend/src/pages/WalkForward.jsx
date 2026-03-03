import { useState } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts'
import { Activity } from 'lucide-react'

const API = ''

const STRATEGIES = [
    { key: 'dual_ma', label: '双均线' },
    { key: 'enhanced_dual_ma', label: '增强双均线' },
    { key: 'macd', label: 'MACD' },
    { key: 'bollinger', label: '布林带' },
    { key: 'multi_factor', label: '多因子' },
    { key: 'turtle', label: '海龟策略' },
]

const PARAM_GRIDS = {
    dual_ma: { short_window: [5, 10, 15], long_window: [20, 30, 60] },
    enhanced_dual_ma: { short_window: [5, 10, 15], long_window: [20, 30, 60], trend_window: [40, 60] },
    macd: { fast_period: [8, 12, 15], slow_period: [20, 26, 30], signal_period: [7, 9] },
    bollinger: { bb_period: [15, 20, 25], bb_std: [1.5, 2.0, 2.5] },
    multi_factor: { min_factors: [3, 4, 5] },
    turtle: { entry_window: [15, 20, 25], exit_window: [8, 10, 12] },
}

function pct(v) {
    if (v === undefined || v === null) return '—'
    return `${(v * 100).toFixed(2)}%`
}

export default function WalkForward() {
    const [symbol, setSymbol] = useState('000001')
    const [strategyKey, setStrategyKey] = useState('dual_ma')
    const [trainDays, setTrainDays] = useState(252)
    const [testDays, setTestDays] = useState(126)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    async function run() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const res = await fetch(`${API}/api/walk-forward`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol.trim(),
                    strategy_name: strategyKey,
                    param_grid: PARAM_GRIDS[strategyKey] || {},
                    train_days: trainDays,
                    test_days: testDays,
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

    const s = result?.summary
    const details = result?.details || []

    // Chart data: per-window out-of-sample return
    const chartData = details.map(d => ({
        name: `窗口${d.window}`,
        样本内收益: +(d.in_sample_return * 100).toFixed(2),
        样本外收益: +(d.out_sample_return * 100).toFixed(2),
    }))

    // Overfit indicator
    function overfitTag(ratio) {
        if (ratio === undefined || ratio === null) return null
        if (ratio > 3) return <span className="tag tag-red">严重过拟合</span>
        if (ratio > 1.5) return <span className="tag tag-gold">轻度过拟合</span>
        return <span className="tag tag-green">稳健</span>
    }

    return (
        <div className="animate-fadein">
            <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Walk-Forward 分析</h1>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 }}>
                滚动窗口训练+验证，检测参数过拟合
            </p>

            {/* Controls */}
            <div className="card" style={{ marginBottom: 24 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 16, alignItems: 'end' }}>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            股票代码
                        </label>
                        <input className="input-field" placeholder="如 000001" value={symbol}
                            onChange={e => setSymbol(e.target.value)} />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            策略选择
                        </label>
                        <select className="select-field" value={strategyKey} onChange={e => setStrategyKey(e.target.value)}>
                            {STRATEGIES.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
                        </select>
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            训练窗口（交易日）
                        </label>
                        <input className="input-field" type="number" value={trainDays}
                            onChange={e => setTrainDays(parseInt(e.target.value) || 252)} />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                            测试窗口（交易日）
                        </label>
                        <input className="input-field" type="number" value={testDays}
                            onChange={e => setTestDays(parseInt(e.target.value) || 126)} />
                    </div>
                    <button className="btn btn-primary" onClick={run} disabled={loading} style={{ height: 38 }}>
                        {loading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Activity size={15} />}
                        {loading ? '分析中…' : '运行分析'}
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
                    <div>正在进行 Walk-Forward 分析，多窗口优化中…</div>
                </div>
            )}

            {result && s && !loading && (
                <>
                    {/* Summary Cards */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                        <div className="card" style={{ padding: '16px 20px' }}>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>滚动窗口数</div>
                            <div style={{ fontSize: 22, fontWeight: 700 }}>{s.total_windows}</div>
                        </div>
                        <div className="card" style={{ padding: '16px 20px' }}>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
                                过拟合比率 {overfitTag(s.overfit_ratio)}
                            </div>
                            <div style={{
                                fontSize: 22, fontWeight: 700,
                                color: s.overfit_ratio > 3 ? 'var(--accent-red)' : s.overfit_ratio > 1.5 ? 'var(--accent-gold)' : 'var(--accent-green)'
                            }}>
                                {s.overfit_ratio?.toFixed(2)}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                                样本内夏普 / 样本外夏普
                            </div>
                        </div>
                        <div className="card" style={{ padding: '16px 20px' }}>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>平均样本外收益</div>
                            <div style={{
                                fontSize: 22, fontWeight: 700,
                                color: s.avg_out_sample_return > 0 ? 'var(--accent-green)' : 'var(--accent-red)'
                            }}>
                                {pct(s.avg_out_sample_return)}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                                窗口正收益率: {pct(s.window_win_rate)}
                            </div>
                        </div>
                        <div className="card" style={{ padding: '16px 20px' }}>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>平均样本外夏普</div>
                            <div style={{
                                fontSize: 22, fontWeight: 700,
                                color: s.avg_out_sample_sharpe > 0 ? 'var(--accent-green)' : 'var(--accent-red)'
                            }}>
                                {s.avg_out_sample_sharpe?.toFixed(3)}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                                样本内夏普: {s.avg_in_sample_sharpe?.toFixed(3)}
                            </div>
                        </div>
                    </div>

                    {/* Bar chart: in-sample vs out-of-sample returns */}
                    <div className="card" style={{ marginBottom: 24 }}>
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>各窗口 样本内 vs 样本外 收益（%）</div>
                        <ResponsiveContainer width="100%" height={260}>
                            <BarChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                <XAxis dataKey="name" tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
                                <Bar dataKey="样本内收益" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="样本外收益" radius={[4, 4, 0, 0]}>
                                    {chartData.map((entry, i) => (
                                        <Cell key={i} fill={entry['样本外收益'] >= 0 ? '#10b981' : '#ef4444'} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Detail Table */}
                    <div className="card">
                        <div style={{ fontWeight: 600, marginBottom: 16 }}>窗口明细</div>
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>窗口</th>
                                        <th>训练期</th>
                                        <th>测试期</th>
                                        <th>最优参数</th>
                                        <th>样本内收益</th>
                                        <th>样本内夏普</th>
                                        <th>样本外收益</th>
                                        <th>样本外夏普</th>
                                        <th>样本外回撤</th>
                                        <th>样本外交易</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {details.map((d, i) => (
                                        <tr key={i}>
                                            <td style={{ fontWeight: 600 }}>{d.window}</td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                                {d.train_start}<br />{d.train_end}
                                            </td>
                                            <td style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                                {d.test_start}<br />{d.test_end}
                                            </td>
                                            <td style={{ fontSize: 11, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                title={d.best_params}>
                                                {d.best_params}
                                            </td>
                                            <td style={{ color: d.in_sample_return > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                                                {pct(d.in_sample_return)}
                                            </td>
                                            <td>{d.in_sample_sharpe?.toFixed(2)}</td>
                                            <td style={{ fontWeight: 600, color: d.out_sample_return > 0 ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                                                {pct(d.out_sample_return)}
                                            </td>
                                            <td style={{ fontWeight: 600 }}>{d.out_sample_sharpe?.toFixed(2)}</td>
                                            <td style={{ color: 'var(--accent-red)' }}>{pct(d.out_sample_max_dd)}</td>
                                            <td style={{ color: 'var(--text-secondary)' }}>{d.out_sample_trades}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {result && !s && !loading && (
                <div className="card" style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                    ⚠️ {result.message || '数据不足以进行 Walk-Forward 分析，请使用更长的数据范围'}
                </div>
            )}
        </div>
    )
}
