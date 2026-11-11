import { createElement, useMemo, useState } from 'react'
import {
    Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer,
    Tooltip, XAxis, YAxis,
} from 'recharts'
import { Activity, AlertTriangle, Calculator, Gauge, Loader2, RadioTower, TrendingUp } from 'lucide-react'

const API = ''

function MetricCard({ icon: Icon, label, value, sub, tone = 'primary' }) {
    const colorMap = {
        primary: 'var(--text-primary)',
        red: 'var(--accent-red)',
        green: 'var(--accent-green)',
        gold: 'var(--accent-gold)',
        blue: 'var(--accent-blue)',
    }
    return (
        <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)', fontSize: 12, marginBottom: 10 }}>
                {createElement(Icon, { size: 15 })}
                {label}
            </div>
            <div style={{ fontSize: 23, fontWeight: 750, color: colorMap[tone], lineHeight: 1.15 }}>{value}</div>
            {sub && <div style={{ marginTop: 6, color: 'var(--text-secondary)', fontSize: 12 }}>{sub}</div>}
        </div>
    )
}

function formatPrice(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
    return Number(v).toFixed(2)
}

function formatSigned(v, suffix = '') {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
    const n = Number(v)
    return `${n > 0 ? '+' : ''}${n.toFixed(2)}${suffix}`
}

function triggerText(row) {
    if (!row) return '未计算'
    if (row.severe_trigger) return '严重异动'
    if (row.ordinary_trigger) return '普通异动'
    return '未触发'
}

export default function AbnormalMovement() {
    const [query, setQuery] = useState('000001')
    const [lookaheadDays, setLookaheadDays] = useState(10)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const chartData = useMemo(() => {
        if (!result?.chart) return []
        return result.chart.map(row => ({
            ...row,
            closeLine: row.type === 'history' ? row.close : null,
            futureOrdinaryUp: row.type === 'future' ? row.ordinary_up_price : null,
            futureSevere10Up: row.type === 'future' ? row.severe_10_up_price : null,
            futureSevere30Up: row.type === 'future' ? row.severe_30_up_price : null,
        }))
    }, [result])

    async function calculate() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const res = await fetch(`${API}/api/abnormal/calculate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query.trim(),
                    lookahead_days: Number(lookaheadDays),
                    history_days: 100,
                }),
            })
            if (!res.ok) {
                const err = await res.json()
                throw new Error(err.detail || '异动计算失败')
            }
            setResult(await res.json())
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    const latest = result?.latest
    const futureRows = result?.future || []
    const statusTone = latest?.severe_trigger ? 'red' : latest?.ordinary_trigger ? 'gold' : 'green'

    return (
        <div className="animate-fadein" style={{ maxWidth: 1280, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start', marginBottom: 22 }}>
                <div>
                    <h1 style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 24, fontWeight: 750, margin: '0 0 8px' }}>
                        <Activity color="var(--accent-gold)" />
                        异动计算
                    </h1>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                        按个股涨跌幅减基准指数涨跌幅计算 3 日、10 日、30 日累计偏离值
                    </div>
                </div>
                {result && (
                    <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 18, fontWeight: 700 }}>{result.stock_name}</div>
                        <div style={{ marginTop: 6 }}>
                            <span className="tag tag-blue">{result.symbol}</span>
                            <span className="tag tag-gold" style={{ marginLeft: 8 }}>{result.board.name}</span>
                        </div>
                    </div>
                )}
            </div>

            <div className="card" style={{ marginBottom: 22 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 1fr) 160px auto', gap: 14, alignItems: 'end' }}>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>股票名称或代码</label>
                        <input className="input-field" value={query} onChange={e => setQuery(e.target.value)} placeholder="如 平安银行 / 000001" />
                    </div>
                    <div>
                        <label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>未来估算天数</label>
                        <input className="input-field" type="number" min="1" max="60" value={lookaheadDays} onChange={e => setLookaheadDays(e.target.value)} />
                    </div>
                    <button className="btn btn-primary" onClick={calculate} disabled={loading} style={{ height: 38, whiteSpace: 'nowrap' }}>
                        {loading ? <Loader2 size={15} className="spinner" /> : <Calculator size={15} />}
                        {loading ? '计算中' : '开始计算'}
                    </button>
                </div>
            </div>

            {error && (
                <div style={{
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 8, padding: '12px 16px', marginBottom: 20, color: 'var(--accent-red)', fontSize: 14
                }}>
                    {error}
                </div>
            )}

            {loading && (
                <div style={{ textAlign: 'center', padding: 64, color: 'var(--text-secondary)' }}>
                    <div className="spinner" style={{ width: 34, height: 34, margin: '0 auto 16px' }} />
                    <div>正在拉取个股与基准指数日线，并计算监管偏离值…</div>
                </div>
            )}

            {result && !loading && (
                <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 14, marginBottom: 22 }}>
                        <MetricCard icon={TrendingUp} label="当前收盘价" value={formatPrice(latest.close)} sub={`交易日 ${latest.date}`} tone="blue" />
                        <MetricCard icon={Gauge} label="30 日累计偏离" value={formatSigned(latest.dev_30d, '%')} sub={`严重阈值 +200% / -70%`} tone={latest.dev_30d >= 200 ? 'red' : 'primary'} />
                        <MetricCard icon={AlertTriangle} label="当前触发状态" value={triggerText(latest)} sub={latest.severe_reasons?.join('、') || latest.ordinary_reason || '滚动窗口未踩线'} tone={statusTone} />
                        <MetricCard icon={RadioTower} label="30 日严重触线" value={formatSigned(latest.severe_30_up_daily_pct, '%')} sub={`目标价 ${formatPrice(latest.severe_30_up_price)}`} tone="gold" />
                    </div>

                    <div className="card" style={{ marginBottom: 22 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                            <div style={{ fontWeight: 650 }}>偏离值与未来触线价格</div>
                            <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{result.benchmark.name} · {result.benchmark.symbol}</div>
                        </div>
                        <ResponsiveContainer width="100%" height={370}>
                            <ComposedChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(42,58,92,0.5)" />
                                <XAxis dataKey="date" tick={{ fill: '#8fa3c4', fontSize: 11 }} minTickGap={20} />
                                <YAxis yAxisId="pct" tick={{ fill: '#8fa3c4', fontSize: 11 }} />
                                <YAxis yAxisId="price" orientation="right" tick={{ fill: '#8fa3c4', fontSize: 11 }} domain={['auto', 'auto']} />
                                <Tooltip
                                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }}
                                    labelStyle={{ color: 'var(--text-secondary)' }}
                                    formatter={(value, name) => {
                                        const labels = {
                                            dev_3d: '3 日累计偏离',
                                            dev_10d: '10 日累计偏离',
                                            dev_30d: '30 日累计偏离',
                                            closeLine: '收盘价',
                                            futureOrdinaryUp: '普通涨异动价',
                                            futureSevere10Up: '10 日严重涨异动价',
                                            futureSevere30Up: '30 日严重涨异动价',
                                        }
                                        const suffix = ['dev_3d', 'dev_10d', 'dev_30d'].includes(name) ? '%' : ''
                                        return [`${formatPrice(value)}${suffix}`, labels[name] || name]
                                    }}
                                />
                                <ReferenceLine yAxisId="pct" y={result.board.ordinary_up} stroke="rgba(245,158,11,0.65)" strokeDasharray="4 4" />
                                <ReferenceLine yAxisId="pct" y={100} stroke="rgba(239,68,68,0.55)" strokeDasharray="4 4" />
                                <ReferenceLine yAxisId="pct" y={200} stroke="rgba(239,68,68,0.35)" strokeDasharray="4 4" />
                                <Area yAxisId="pct" type="monotone" dataKey="dev_3d" fill="rgba(245,158,11,0.12)" stroke="#f59e0b" dot={false} />
                                <Line yAxisId="pct" type="monotone" dataKey="dev_10d" stroke="#ef4444" strokeWidth={1.8} dot={false} connectNulls={false} />
                                <Line yAxisId="pct" type="monotone" dataKey="dev_30d" stroke="#8b5cf6" strokeWidth={1.6} dot={false} connectNulls={false} />
                                <Line yAxisId="price" type="monotone" dataKey="closeLine" stroke="#3b82f6" strokeWidth={2} dot={false} connectNulls={false} />
                                <Line yAxisId="price" type="monotone" dataKey="futureOrdinaryUp" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2 }} connectNulls={false} />
                                <Line yAxisId="price" type="monotone" dataKey="futureSevere10Up" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2 }} connectNulls={false} />
                                <Line yAxisId="price" type="monotone" dataKey="futureSevere30Up" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2 }} connectNulls={false} />
                                {futureRows[0] && <ReferenceLine x={futureRows[0].date} stroke="rgba(143,163,196,0.6)" strokeDasharray="4 4" />}
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 18, alignItems: 'start' }}>
                        <div className="card">
                            <div style={{ fontWeight: 650, marginBottom: 14 }}>未来交易日触线价格</div>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>日期</th>
                                        <th>30 日基准日</th>
                                        <th>普通涨异动价</th>
                                        <th>普通跌异动价</th>
                                        <th>10 日严重价</th>
                                        <th>30 日严重价</th>
                                        <th>30 日需涨幅</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {futureRows.map(row => (
                                        <tr key={row.date}>
                                            <td>{row.date}</td>
                                            <td>{row.severe_30_base_date || '--'}</td>
                                            <td style={{ color: 'var(--accent-gold)', fontWeight: 650 }}>{formatPrice(row.ordinary_up_price)}</td>
                                            <td style={{ color: 'var(--accent-green)', fontWeight: 650 }}>{formatPrice(row.ordinary_down_price)}</td>
                                            <td style={{ color: 'var(--accent-red)', fontWeight: 650 }}>{formatPrice(row.severe_10_up_price)}</td>
                                            <td style={{ color: '#a78bfa', fontWeight: 650 }}>{formatPrice(row.severe_30_up_price)}</td>
                                            <td style={{ color: '#a78bfa', fontWeight: 650 }}>{formatSigned(row.severe_30_up_pct, '%')}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                            <div className="card">
                                <div style={{ fontWeight: 650, marginBottom: 12 }}>最近普通异动记录</div>
                                {result.events.length === 0 ? (
                                    <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>最近窗口内未记录普通异动</div>
                                ) : result.events.map(event => (
                                    <div key={`${event.date}-${event.direction}`} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(42,58,92,0.5)', fontSize: 13 }}>
                                        <span>{event.date}</span>
                                        <span className={event.direction === 'up' ? 'metric-up' : event.direction === 'down' ? 'metric-down' : 'metric-neutral'}>{event.reason}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="card">
                                <div style={{ fontWeight: 650, marginBottom: 12 }}>计算说明</div>
                                {result.notes.map(note => (
                                    <div key={note} style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6, marginBottom: 8 }}>{note}</div>
                                ))}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
