import { useState, useEffect } from 'react'
import { Clock, Zap, Diamond, TrendingUp, TrendingDown, Search, Loader2, AlertTriangle, Heart } from 'lucide-react'
import useWebSocket from '../hooks/useWebSocket'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

function getTimeHint() {
    const now = new Date()
    const h = now.getHours()
    const m = now.getMinutes()
    const time = h * 100 + m

    if (time >= 920 && time <= 930) {
        return { text: '🔥 集合竞价时段 — 捕捉早盘最强动能', color: 'var(--accent-red)', tab: 'auction' }
    } else if (time >= 1430 && time <= 1500) {
        return { text: '🌙 尾盘时段 — 寻找隔夜套利机会', color: 'var(--accent-blue)', tab: 'overnight' }
    } else if (time > 930 && time < 1430) {
        return { text: '⚡ 盘中时段 — 依据开盘/盘中数据测算', color: 'var(--accent-gold)', tab: null }
    }
    return { text: '💤 非交易时段 — 数据为上一交易日', color: 'var(--text-secondary)', tab: null }
}

function StockTable({ stocks, type, watchlistSet, onAddWatchlist, onBatchAddWatchlist }) {
    if (!stocks || stocks.length === 0) {
        return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>暂无符合条件的股票</div>
    }

    return (
        <div style={{ overflowX: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 16px 16px 16px' }}>
                <button className="btn btn-outline" style={{ fontSize: 13, height: 32, padding: '0 12px' }} onClick={() => onBatchAddWatchlist(stocks)}>
                    <Heart size={14} style={{ marginRight: 6 }} /> 批量加入自选
                </button>
            </div>
            <table className="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>代码</th>
                        <th>名称</th>
                        <th>现价</th>
                        {type === 'auction' && <th>开盘涨跌%</th>}
                        <th>涨跌幅%</th>
                        <th>量比</th>
                        <th>换手率%</th>
                        <th>流通市值(亿)</th>
                        <th>PE</th>
                        {type === 'overnight' && <th>振幅%</th>}
                        <th>综合评分</th>
                        <th>自选</th>
                    </tr>
                </thead>
                <tbody>
                    {stocks.map((s, i) => {
                        const pctVal = type === 'auction' ? s.open_pct : s.change_pct
                        const isUp = pctVal > 0
                        const isWatched = watchlistSet.has(s.code)
                        return (
                            <tr key={s.code} className="animate-fadein" style={{ animationDelay: `${i * 30}ms` }}>
                                <td style={{ fontWeight: 700, color: i < 3 ? 'var(--accent-gold)' : 'var(--text-secondary)' }}>{i + 1}</td>
                                <td style={{ fontFamily: 'monospace' }}>{s.code}</td>
                                <td style={{ fontWeight: 600 }}>{s.name}</td>
                                <td>{s.price.toFixed(2)}</td>
                                {type === 'auction' && (
                                    <td style={{ color: s.open_pct > 0 ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 600 }}>
                                        {s.open_pct > 0 ? '+' : ''}{s.open_pct.toFixed(2)}%
                                    </td>
                                )}
                                <td style={{ color: s.change_pct > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                                    {s.change_pct > 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                                </td>
                                <td><span className={s.volume_ratio >= 2 ? 'tag tag-gold' : ''}>{s.volume_ratio.toFixed(1)}</span></td>
                                <td>{s.turnover.toFixed(1)}%</td>
                                <td>{s.market_cap.toFixed(0)}</td>
                                <td>{s.pe.toFixed(1)}</td>
                                {type === 'overnight' && <td>{(s.amplitude || 0).toFixed(1)}%</td>}
                                <td>
                                    <span style={{
                                        background: s.score >= 60 ? 'rgba(16,185,129,0.15)' : s.score >= 40 ? 'rgba(245,158,11,0.15)' : 'rgba(239,68,68,0.1)',
                                        color: s.score >= 60 ? 'var(--accent-red)' : s.score >= 40 ? 'var(--accent-gold)' : 'var(--accent-green)',
                                        padding: '2px 8px', borderRadius: 4, fontWeight: 700, fontSize: 13,
                                    }}>
                                        {s.score.toFixed(0)}
                                    </span>
                                </td>
                                <td>
                                    <button
                                        className="icon-btn"
                                        style={{ color: isWatched ? 'var(--accent-red)' : 'var(--text-secondary)', opacity: isWatched ? 1 : 0.5 }}
                                        onClick={() => onAddWatchlist(s, isWatched)}
                                        title={isWatched ? "取消自选" : "加入自选"}
                                    >
                                        <Heart size={15} fill={isWatched ? 'var(--accent-red)' : 'none'} />
                                    </button>
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}

export default function TimingPicker() {
    const [tab, setTab] = useState('auction')
    const [mode, setMode] = useState('attack')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [manualResult, setManualResult] = useState(null) // 手动触发的结果
    const { timing: wsTiming, status: wsStatus, lastUpdate: wsLastUpdate } = useWebSocket()
    const [watchlistSet, setWatchlistSet] = useState(new Set())

    const timeHint = getTimeHint()

    // 根据当前 tab + mode 从 WebSocket 数据中取实时结果
    const wsKey = `${tab}_${mode}`  // e.g. "auction_attack"
    const wsResult = wsTiming?.[wsKey] || null

    // 优先显示实时数据（如果有），否则显示手动结果
    const result = wsResult || manualResult

    // 加载初始自选状态
    useEffect(() => {
        fetch(`${API}/watchlist`).then(r => r.json()).then(data => {
            if (data.stocks) {
                setWatchlistSet(new Set(data.stocks.map(s => s.code)))
            }
        }).catch(e => console.error(e))
    }, [])

    const handleAddWatchlist = async (s, isWatched) => {
        try {
            if (isWatched) {
                const res = await fetch(`${API}/watchlist/${s.code}`, { method: 'DELETE' })
                if (res.ok) {
                    setWatchlistSet(prev => {
                        const next = new Set(prev)
                        next.delete(s.code)
                        return next
                    })
                }
            } else {
                const groupName = tab === 'auction' ? '竞价狙击' : '尾盘隔夜'
                const res = await fetch(`${API}/watchlist`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: s.code, name: s.name, holding: false, group: groupName })
                })
                if (res.ok) {
                    setWatchlistSet(prev => new Set(prev).add(s.code))
                }
            }
        } catch (e) {
            alert('操作自选失败')
        }
    }

    const handleBatchAddWatchlist = async (stocks) => {
        const toAdd = stocks.filter(s => !watchlistSet.has(s.code))
        if (toAdd.length === 0) {
            alert('当前列表股票都已在自选中')
            return
        }

        const groupName = tab === 'auction' ? '竞价狙击' : '尾盘隔夜'
        const payload = {
            stocks: toAdd.map(s => ({
                code: s.code,
                name: s.name,
                holding: false,
                group: groupName
            }))
        }

        try {
            const res = await fetch(`${API}/watchlist/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            if (res.ok) {
                alert(`已成功批量加入 ${toAdd.length} 只股票至自选（分组：${groupName}）`)
                setWatchlistSet(prev => {
                    const next = new Set(prev)
                    toAdd.forEach(s => next.add(s.code))
                    return next
                })
            }
        } catch (e) {
            alert('批量加入自选失败')
        }
    }

    const fetchData = async (t = tab, m = mode) => {
        setLoading(true)
        setError(null)
        setManualResult(null)
        try {
            const endpoint = t === 'auction' ? 'auction' : 'overnight'
            const res = await fetch(`${API}/timing-picker/${endpoint}?mode=${m}&top_n=20`)
            if (!res.ok) throw new Error('网络请求失败')
            const json = await res.json()
            if (json.error) throw new Error(json.error)
            setManualResult(json)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const switchTab = (t) => {
        setTab(t)
        setMode('attack')
        setManualResult(null)
    }

    const switchMode = (m) => {
        setMode(m)
        setManualResult(null)
    }

    return (
        <div style={{ maxWidth: 1200, margin: '0 auto' }} className="animate-fadein">
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Clock color="var(--accent-gold)" />
                        时机选股
                    </h1>
                    <div style={{ color: timeHint.color, fontSize: 14, fontWeight: 500 }}>
                        {timeHint.text}
                        {wsStatus === 'connected' && (
                            <span style={{ marginLeft: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block', marginRight: 4, boxShadow: '0 0 6px #10b981' }}></span>
                                实时{wsLastUpdate && ` · ${wsLastUpdate}`}
                            </span>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Tabs */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
                <button
                    className={`btn ${tab === 'auction' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => switchTab('auction')}
                    style={{ fontSize: 15, padding: '10px 20px' }}
                >
                    <Zap size={16} /> 竞价狙击
                    <span style={{ fontSize: 11, opacity: 0.7, marginLeft: 4 }}>9:25-9:30</span>
                </button>
                <button
                    className={`btn ${tab === 'overnight' ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => switchTab('overnight')}
                    style={{ fontSize: 15, padding: '10px 20px' }}
                >
                    <Clock size={16} /> 尾盘隔夜
                    <span style={{ fontSize: 11, opacity: 0.7, marginLeft: 4 }}>14:30-15:00</span>
                </button>
            </div>

            {/* Mode + Run */}
            <div className="card" style={{ padding: '16px 20px', marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button
                            className="btn"
                            style={{
                                background: mode === 'attack' ? 'rgba(239,68,68,0.15)' : 'transparent',
                                color: mode === 'attack' ? 'var(--accent-red)' : 'var(--text-secondary)',
                                border: `1px solid ${mode === 'attack' ? 'var(--accent-red)' : 'var(--border)'}`,
                            }}
                            onClick={() => switchMode('attack')}
                        >
                            <TrendingUp size={14} />
                            🔥 {tab === 'auction' ? '攻势追强' : '强势隔夜'}
                        </button>
                        <button
                            className="btn"
                            style={{
                                background: mode === 'bargain' ? 'rgba(59,130,246,0.15)' : 'transparent',
                                color: mode === 'bargain' ? 'var(--accent-blue)' : 'var(--text-secondary)',
                                border: `1px solid ${mode === 'bargain' ? 'var(--accent-blue)' : 'var(--border)'}`,
                            }}
                            onClick={() => switchMode('bargain')}
                        >
                            <TrendingDown size={14} />
                            💎 {tab === 'auction' ? '低吸抄底' : '跌幅捡筹'}
                        </button>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                            {mode === 'attack'
                                ? (tab === 'auction' ? '高开 1%-7%, 量比≥2' : '涨幅 2%-7%, 量价齐升')
                                : (tab === 'auction' ? '低开 -5%~-1%, 有承接' : '跌幅 -5%~-1%, PE低估')
                            }
                        </div>
                        <button className="btn btn-gold" onClick={() => fetchData()} disabled={loading}>
                            {loading ? <Loader2 size={16} className="spinner" /> : <Search size={16} />}
                            开始选股
                        </button>
                    </div>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', borderLeft: '4px solid var(--accent-red)', padding: '12px 16px', marginBottom: 20, borderRadius: '0 8px 8px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
                    <AlertTriangle color="var(--accent-red)" size={20} /> {error}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="card" style={{ padding: 40, textAlign: 'center' }}>
                    <div className="spinner" style={{ margin: '0 auto 12px' }}></div>
                    <div style={{ color: 'var(--text-secondary)' }}>正在扫描全市场行情数据...</div>
                </div>
            )}

            {/* Results */}
            {result && !loading && (
                <div className="card animate-fadein" style={{ padding: 0, overflow: 'hidden' }}>
                    {/* Summary bar */}
                    <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '14px 20px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <span style={{ fontSize: 16, fontWeight: 700 }}>
                                {result.config?.label}
                            </span>
                            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                                {result.config?.desc}
                            </span>
                            {wsResult && (
                                <span style={{ fontSize: 11, background: 'rgba(16,185,129,0.15)', color: '#10b981', padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                                    🔴 LIVE {wsLastUpdate}
                                </span>
                            )}
                        </div>
                        <div style={{ display: 'flex', gap: 16, fontSize: 13 }}>
                            <span style={{ color: 'var(--text-secondary)' }}>扫描: <strong style={{ color: 'var(--text-primary)' }}>{result.total_scanned}</strong> 只</span>
                            <span style={{ color: 'var(--text-secondary)' }}>命中: <strong style={{ color: 'var(--accent-gold)' }}>{result.total_matched}</strong> 只</span>
                        </div>
                    </div>
                    <div style={{ padding: 16 }}>
                        <StockTable
                            stocks={result.stocks}
                            type={tab}
                            watchlistSet={watchlistSet}
                            onAddWatchlist={handleAddWatchlist}
                            onBatchAddWatchlist={handleBatchAddWatchlist}
                        />
                    </div>
                </div>
            )}

            {/* Tips — 只在无实时数据且无手动结果时显示 */}
            {!result && !loading && !error && (
                <div className="card" style={{ padding: '40px 20px', textAlign: 'center' }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>{tab === 'auction' ? '🔔' : '🌙'}</div>
                    <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                        {tab === 'auction' ? '盘前竞价选股' : '尾盘一夜持股法'}
                    </div>
                    <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 500, margin: '0 auto' }}>
                        {wsStatus === 'connected'
                            ? '盘中实时数据推送中，等待首次刷新...'
                            : tab === 'auction'
                                ? '选择「追强」或「抄底」模式后点击"开始选股"。最佳使用时间：9:25 集合竞价结束后。'
                                : '选择「强势隔夜」或「跌幅捡筹」模式后点击"开始选股"。最佳使用时间：14:30-14:55 尾盘时段。'
                        }
                    </div>
                </div>
            )}
        </div>
    )
}
