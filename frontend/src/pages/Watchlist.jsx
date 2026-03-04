import { useState, useRef, useEffect } from 'react'
import { Brain, Send, AlertTriangle, Plus, Trash2, Edit2, Play, ChevronDown, ChevronRight, X, Heart, ShieldAlert, LineChart } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export default function Watchlist() {
    const [stocks, setStocks] = useState([])
    const [loadingList, setLoadingList] = useState(false)
    const [selectedStocks, setSelectedStocks] = useState(new Set())

    // Right panel state
    const [selectedStock, setSelectedStock] = useState(null)
    const [analyzeMode, setAnalyzeMode] = useState('single') // single / portfolio

    // Single analysis state
    const [singleLoading, setSingleLoading] = useState(false)
    const [singleStatus, setSingleStatus] = useState('')
    const [singleMeta, setSingleMeta] = useState(null)
    const [singleReport, setSingleReport] = useState('')
    const singleAbortRef = useRef(null)
    const singleReportRef = useRef(null)

    // Portfolio analysis state
    const [portLoading, setPortLoading] = useState(false)
    const [portStatus, setPortStatus] = useState('')
    const [portMeta, setPortMeta] = useState(null)
    const [portReport, setPortReport] = useState('')
    const portAbortRef = useRef(null)
    const portReportRef = useRef(null)

    // Add stock modal / form
    const [showAddForm, setShowAddForm] = useState(false)
    const [addForm, setAddForm] = useState({
        code: '', name: '', holding: false, cost_price: 0, position_pct: 0, horizon: 'short'
    })

    // Load watchlist
    const fetchWatchlist = async () => {
        setLoadingList(true)
        try {
            const res = await fetch(`${API}/watchlist`)
            if (res.ok) {
                const data = await res.json()
                setStocks(data.stocks || [])
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoadingList(false)
        }
    }

    useEffect(() => {
        fetchWatchlist()
    }, [])

    // Auto scroll
    useEffect(() => { if (singleReportRef.current) singleReportRef.current.scrollTop = singleReportRef.current.scrollHeight }, [singleReport])
    useEffect(() => { if (portReportRef.current) portReportRef.current.scrollTop = portReportRef.current.scrollHeight }, [portReport])

    // --- CRUD Actions ---

    const handleSaveStock = async () => {
        if (!addForm.code) return
        try {
            await fetch(`${API}/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(addForm)
            })
            await fetchWatchlist()
            setShowAddForm(false)
            if (selectedStock && selectedStock.code === addForm.code) {
                setSelectedStock({ ...addForm })
            }
        } catch (e) {
            alert("保存失败")
        }
    }

    const handleDeleteStock = async (code) => {
        if (!confirm(`确定要移除 ${code} 吗？`)) return
        try {
            await fetch(`${API}/watchlist/${code}`, { method: 'DELETE' })
            await fetchWatchlist()
            if (selectedStock && selectedStock.code === code) setSelectedStock(null)
        } catch (e) {
            alert("移除失败")
        }
    }

    const handleBatchDelete = async () => {
        if (selectedStocks.size === 0) return
        if (!confirm(`确定要移除选中的 ${selectedStocks.size} 只股票吗？`)) return
        try {
            const res = await fetch(`${API}/watchlist/batch-delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ codes: Array.from(selectedStocks) })
            })
            if (res.ok) {
                await fetchWatchlist()
                if (selectedStock && selectedStocks.has(selectedStock.code)) {
                    setSelectedStock(null)
                }
                setSelectedStocks(new Set())
            }
        } catch (e) {
            alert("批量移除失败")
        }
    }


    // --- Analyze Actions ---

    const handleSingleAnalyze = async (stock = selectedStock) => {
        if (!stock) return
        setAnalyzeMode('single')
        setSelectedStock(stock)

        setSingleLoading(true)
        setSingleStatus('正在连接...')
        setSingleMeta(null)
        setSingleReport('')

        const ctrl = new AbortController()
        singleAbortRef.current = ctrl

        try {
            const resp = await fetch(`${API}/watchlist/analyze/single`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: stock.code,
                    holding: stock.holding || false,
                    cost_price: stock.cost_price || 0,
                    position_pct: stock.position_pct || 0,
                    horizon: stock.horizon || ''
                }),
                signal: ctrl.signal,
            })

            const reader = resp.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { value, done } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop()

                let eventType = ''
                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        eventType = line.slice(7)
                    } else if (line.startsWith('data: ') && eventType === 'event') {
                        try {
                            const data = JSON.parse(line.slice(6))
                            if (data.type === 'status') {
                                setSingleStatus(data.message)
                            } else if (data.type === 'meta') {
                                setSingleMeta(data)
                                setSingleStatus('AI 正在撰写报告...')
                            } else if (data.type === 'token') {
                                setSingleReport(prev => prev + data.content)
                            } else if (data.type === 'done') {
                                setSingleStatus('')
                            } else if (data.type === 'error') {
                                setSingleStatus(`❌ ${data.message}`)
                            }
                        } catch { /* ignore */ }
                    }
                }
            }
        } catch (e) {
            if (e.name !== 'AbortError') setSingleStatus(`❌ 请求失败: ${e.message}`)
        } finally {
            setSingleLoading(false)
        }
    }

    const handlePortfolioAnalyze = async () => {
        setAnalyzeMode('portfolio')
        setPortLoading(true)
        setPortStatus('正在连接...')
        setPortMeta(null)
        setPortReport('')

        const ctrl = new AbortController()
        portAbortRef.current = ctrl

        try {
            const resp = await fetch(`${API}/watchlist/analyze/portfolio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days: 365, codes: Array.from(selectedStocks) }),
                signal: ctrl.signal,
            })

            const reader = resp.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { value, done } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop()

                let eventType = ''
                for (const line of lines) {
                    if (line.startsWith('event: ')) {
                        eventType = line.slice(7)
                    } else if (line.startsWith('data: ') && eventType === 'event') {
                        try {
                            const data = JSON.parse(line.slice(6))
                            if (data.type === 'status') {
                                setPortStatus(data.message)
                            } else if (data.type === 'meta') {
                                setPortMeta(data)
                                setPortStatus('AI 正在进行组合体检...')
                            } else if (data.type === 'token') {
                                setPortReport(prev => prev + data.content)
                            } else if (data.type === 'done') {
                                setPortStatus('')
                            } else if (data.type === 'error') {
                                setPortStatus(`❌ ${data.message}`)
                            }
                        } catch { /* ignore */ }
                    }
                }
            }
        } catch (e) {
            if (e.name !== 'AbortError') setPortStatus(`❌ 请求失败: ${e.message}`)
        } finally {
            setPortLoading(false)
        }
    }

    const stopSingle = () => { if (singleAbortRef.current) { singleAbortRef.current.abort(); setSingleLoading(false); setSingleStatus('已停止') } }
    const stopPort = () => { if (portAbortRef.current) { portAbortRef.current.abort(); setPortLoading(false); setPortStatus('已停止') } }

    // ───────── UI 组件 ─────────

    const renderStockList = () => {
        // 分组处理逻辑
        const groupedStocks = {}
        stocks.forEach(s => {
            const g = s.group || '默认自选'
            if (!groupedStocks[g]) groupedStocks[g] = []
            groupedStocks[g].push(s)
        })

        return (
            <div className="card" style={{ flex: '0 0 320px', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 104px)' }}>
                <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Heart size={18} color="var(--accent-red)" /> 自选股
                    </h2>
                    <div style={{ display: 'flex', gap: 8 }}>
                        {selectedStocks.size > 0 && (
                            <button className="btn btn-outline" style={{ padding: '4px 8px', fontSize: 12, color: 'var(--accent-red)', borderColor: 'var(--accent-red)' }} onClick={handleBatchDelete}>
                                <Trash2 size={14} /> 删除({selectedStocks.size})
                            </button>
                        )}
                        <button className="btn btn-outline" style={{ padding: '4px 8px', fontSize: 12 }} onClick={() => {
                            setAddForm({ code: '', name: '', holding: false, cost_price: 0, position_pct: 0, horizon: 'short', group: '默认自选' });
                            setShowAddForm(true);
                        }}>
                            <Plus size={14} /> 添加
                        </button>
                    </div>
                </div>

                <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
                    {loadingList && stocks.length === 0 ? <div className="spinner" style={{ margin: '40px auto' }}></div> : null}

                    {stocks.length === 0 && !loadingList && (
                        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-secondary)' }}>
                            暂无自选股，点击添加
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {Object.entries(groupedStocks).map(([groupName, groupStocks]) => (
                            <div key={groupName}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, paddingLeft: 4 }}>
                                    {groupName} ({groupStocks.length})
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                    {groupStocks.map(s => (
                                        <div
                                            key={s.code}
                                            style={{
                                                padding: '12px 16px',
                                                borderRadius: 8,
                                                background: selectedStock?.code === s.code && analyzeMode === 'single' ? 'var(--bg-active)' : 'transparent',
                                                border: `1px solid ${selectedStock?.code === s.code && analyzeMode === 'single' ? 'var(--accent-gold)' : 'var(--border)'}`,
                                                cursor: 'pointer',
                                                transition: 'all 0.2s',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center'
                                            }}
                                            onClick={() => { setSelectedStock(s); setAnalyzeMode('single'); }}
                                        >
                                            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedStocks.has(s.code)}
                                                    onChange={(e) => {
                                                        const next = new Set(selectedStocks)
                                                        if (e.target.checked) next.add(s.code)
                                                        else next.delete(s.code)
                                                        setSelectedStocks(next)
                                                    }}
                                                    onClick={(e) => e.stopPropagation()}
                                                    style={{ width: 14, height: 14, cursor: 'pointer', flexShrink: 0 }}
                                                />
                                                <div>
                                                    <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
                                                        {s.name || s.code} <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text-secondary)' }}>{s.code}</span>
                                                    </div>
                                                    <div style={{ fontSize: 12 }}>
                                                        {s.holding ? (
                                                            <span style={{ color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                                <ShieldAlert size={12} /> 持仓 · 成本 {s.cost_price} · 占比 {s.position_pct}%
                                                            </span>
                                                        ) : (
                                                            <span style={{ color: 'var(--text-secondary)' }}>👀 仅关注</span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: 6 }}>
                                                <button className="icon-btn" onClick={(e) => { e.stopPropagation(); setAddForm({ ...s, group: s.group || '默认自选' }); setShowAddForm(true); }} title="编辑">
                                                    <Edit2 size={14} />
                                                </button>
                                                <button className="icon-btn" style={{ color: 'var(--accent-red)' }} onClick={(e) => { e.stopPropagation(); handleDeleteStock(s.code); }} title="删除">
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* 组合分析按钮 (固定在左侧底部) */}
                {stocks.filter(s => s.holding).length > 0 && (
                    <div style={{ padding: 16, borderTop: '1px solid var(--border)' }}>
                        <button
                            className={`btn ${analyzeMode === 'portfolio' ? 'btn-primary' : 'btn-outline'}`}
                            style={{ width: '100%', padding: '12px', background: analyzeMode === 'portfolio' ? 'var(--accent-gold)' : '' }}
                            onClick={() => handlePortfolioAnalyze()}
                        >
                            <Brain size={16} /> {selectedStocks.size > 0 ? `对选中的 ${selectedStocks.size} 只股进行组合体检` : '对全部持仓组合进行体检'}
                        </button>
                    </div>
                )}
            </div>
        )
    }

    const renderAddForm = () => (
        showAddForm && (
            <div style={{
                position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                background: 'rgba(0,0,0,0.5)', zIndex: 100,
                display: 'flex', alignItems: 'center', justifyContent: 'center'
            }} className="animate-fadein">
                <div className="card" style={{ width: 400, padding: 0, overflow: 'hidden' }}>
                    <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
                        <h3 style={{ margin: 0 }}>添加/编辑自选股</h3>
                        <button className="icon-btn" onClick={() => setShowAddForm(false)}><X size={18} /></button>
                    </div>
                    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                        <div style={{ display: 'flex', gap: 12 }}>
                            <div style={{ flex: 1 }}>
                                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>股票代码</label>
                                <input className="input-field" style={{ width: '100%' }} value={addForm.code} onChange={e => setAddForm({ ...addForm, code: e.target.value })} placeholder="如 000001" />
                            </div>
                            <div style={{ flex: 1 }}>
                                <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>股票名称</label>
                                <input className="input-field" style={{ width: '100%' }} value={addForm.name} onChange={e => setAddForm({ ...addForm, name: e.target.value })} placeholder="如 平安银行" />
                            </div>
                        </div>

                        <div>
                            <label style={{ display: 'block', fontSize: 13, marginBottom: 6, color: 'var(--text-secondary)' }}>所属分组</label>
                            <input className="input-field" style={{ width: '100%' }} value={addForm.group || ''} onChange={e => setAddForm({ ...addForm, group: e.target.value })} placeholder="如 默认自选" />
                        </div>

                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                            <input type="checkbox" checked={addForm.holding} onChange={e => setAddForm({ ...addForm, holding: e.target.checked })} style={{ width: 16, height: 16 }} />
                            <span style={{ fontWeight: 600 }}>我持有这只股票</span>
                        </label>

                        {addForm.holding && (
                            <div style={{ background: 'var(--bg-secondary)', padding: 16, borderRadius: 8, display: 'flex', flexDirection: 'column', gap: 12 }}>
                                <div style={{ display: 'flex', gap: 12 }}>
                                    <div style={{ flex: 1 }}>
                                        <label style={{ display: 'block', fontSize: 12, marginBottom: 6, color: 'var(--text-secondary)' }}>持仓均价 (元)</label>
                                        <input className="input-field" type="number" style={{ width: '100%' }} value={addForm.cost_price} onChange={e => setAddForm({ ...addForm, cost_price: parseFloat(e.target.value) || 0 })} />
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <label style={{ display: 'block', fontSize: 12, marginBottom: 6, color: 'var(--text-secondary)' }}>仓位占比 (%)</label>
                                        <input className="input-field" type="number" style={{ width: '100%' }} value={addForm.position_pct} onChange={e => setAddForm({ ...addForm, position_pct: parseFloat(e.target.value) || 0 })} />
                                    </div>
                                </div>
                                <div>
                                    <label style={{ display: 'block', fontSize: 12, marginBottom: 6, color: 'var(--text-secondary)' }}>预期投资周期</label>
                                    <select className="input-field" style={{ width: '100%' }} value={addForm.horizon} onChange={e => setAddForm({ ...addForm, horizon: e.target.value })}>
                                        <option value="short">短线交易 (&lt;2周)</option>
                                        <option value="mid">中线波段 (1-3个月)</option>
                                        <option value="long">长线投资 (&gt;半年)</option>
                                    </select>
                                </div>
                            </div>
                        )}

                        <button className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} onClick={handleSaveStock}>
                            保存到自选
                        </button>
                    </div>
                </div>
            </div>
        )
    )

    const renderSinglePanel = () => {
        if (!selectedStock) return (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
                <LineChart size={48} style={{ opacity: 0.2, marginBottom: 16 }} />
                <p>在左侧选择一只自选股进行分析</p>
            </div>
        )

        return (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingLeft: 24, overflowY: 'auto', height: 'calc(100vh - 104px)' }} className="animate-fadein">
                <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ fontSize: 24, margin: '0 0 4px' }}>{selectedStock.name || selectedStock.code} <span style={{ fontSize: 16, color: 'var(--text-secondary)' }}>{selectedStock.code}</span></h2>
                        {selectedStock.holding ? (
                            <div style={{ display: 'flex', gap: 12, fontSize: 13, color: 'var(--text-secondary)' }}>
                                <span>成本: <b>{selectedStock.cost_price}</b></span>
                                <span>仓位: <b>{selectedStock.position_pct}%</b></span>
                                <span>周期: <b>{selectedStock.horizon === 'short' ? '短线' : selectedStock.horizon === 'mid' ? '中线' : '长线'}</b></span>
                            </div>
                        ) : <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>尚未持仓</div>}
                    </div>
                    <div>
                        {!singleLoading ? (
                            <button className="btn btn-primary" onClick={() => handleSingleAnalyze()}>
                                <Brain size={16} /> 诊断个股{selectedStock.holding ? ' (基于持仓)' : ''}
                            </button>
                        ) : (
                            <button className="btn btn-outline" style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)' }} onClick={stopSingle}>停止分析</button>
                        )}
                    </div>
                </div>

                {singleLoading && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><div className="spinner" />{singleStatus}</div>}
                {!singleLoading && singleStatus && <div style={{ fontSize: 13, color: 'var(--accent-red)', marginBottom: 16 }}>{singleStatus}</div>}

                {/* Indicators Card (Reused from old Analyst) */}
                {singleMeta && (
                    <div className="card" style={{ padding: '16px 20px', marginBottom: 20, background: 'var(--bg-secondary)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div style={{ fontSize: 28, fontWeight: 700 }}>
                                {singleMeta.price ?? '--'}
                                {singleMeta.change_pct != null && (
                                    <span className={singleMeta.change_pct >= 0 ? 'metric-up' : 'metric-down'} style={{ fontSize: 16, fontWeight: 600, marginLeft: 12 }}>
                                        {singleMeta.change_pct >= 0 ? '+' : ''}{singleMeta.change_pct.toFixed(2)}%
                                    </span>
                                )}
                            </div>
                            <div style={{ display: 'flex', gap: 8 }}>
                                {singleMeta.trend && <span className={`tag ${singleMeta.trend === '看多' ? 'tag-red' : singleMeta.trend === '看空' ? 'tag-green' : 'tag-blue'}`}>{singleMeta.trend}</span>}
                                {singleMeta.tech_score != null && <span className="tag tag-gold">技术评分 {singleMeta.tech_score}</span>}
                            </div>
                        </div>
                        {/* Some minimal indicators */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
                            <div>PE: <strong style={{ color: 'var(--text-primary)' }}>{singleMeta.valuation?.pe?.toFixed(2) || '--'}</strong></div>
                            <div>市值: <strong style={{ color: 'var(--text-primary)' }}>{singleMeta.market?.cap ? (singleMeta.market.cap / 1e8).toFixed(0) + '亿' : '--'}</strong></div>
                            <div>换手率: <strong style={{ color: 'var(--text-primary)' }}>{singleMeta.market?.turnover?.toFixed(2) || '--'}%</strong></div>
                            <div>量比: <strong style={{ color: 'var(--text-primary)' }}>{singleMeta.market?.volume_ratio?.toFixed(2) || '--'}</strong></div>
                        </div>
                    </div>
                )}

                {/* Report */}
                {(singleReport || singleLoading) && (
                    <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <div style={{ fontSize: 15, fontWeight: 600, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>📝 诊断报告</div>
                        <div ref={singleReportRef} className="markdown-body" style={{ flex: 1, overflowY: 'auto', padding: '16px 0', lineHeight: 1.75 }}>
                            <ReactMarkdown>{singleReport || (singleLoading ? '分析中...' : '')}</ReactMarkdown>
                            {singleLoading && singleReport && <span className="cursor-blink">▍</span>}
                        </div>
                    </div>
                )}
            </div>
        )
    }

    const renderPortfolioPanel = () => {
        return (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingLeft: 24, overflowY: 'auto', height: 'calc(100vh - 104px)' }} className="animate-fadein">
                <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ fontSize: 24, margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 10 }}>
                            <Brain size={24} color="var(--accent-gold)" /> 持仓组合体检
                        </h2>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>综合分析你当前的所有持仓，评估结构风险与调仓建议</div>
                    </div>
                    <div>
                        {portLoading && <button className="btn btn-outline" style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)' }} onClick={stopPort}>停止分析</button>}
                    </div>
                </div>

                {portLoading && <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><div className="spinner" />{portStatus}</div>}
                {!portLoading && portStatus && <div style={{ fontSize: 13, color: 'var(--accent-red)', marginBottom: 16 }}>{portStatus}</div>}

                {/* Portfolio Meta */}
                {portMeta && (
                    <div className="card" style={{ padding: '16px 20px', marginBottom: 20, background: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>总计仓位占用: <span style={{ color: 'var(--accent-gold)', fontSize: 18 }}>{portMeta.total_pct}%</span></div>
                        <table className="data-table" style={{ background: 'transparent' }}>
                            <thead><tr><th>代码</th><th>名称</th><th>持仓占比</th><th>成本价 / 现价</th><th>短期技术趋势</th></tr></thead>
                            <tbody>
                                {portMeta.holdings?.map(h => (
                                    <tr key={h.code}>
                                        <td style={{ fontFamily: 'monospace' }}>{h.code}</td>
                                        <td style={{ fontWeight: 600 }}>{h.name}</td>
                                        <td>{h.position_pct}%</td>
                                        <td>{h.cost_price} / <b>{h.curr_price}</b></td>
                                        <td><span className={`tag ${h.trend === '看多' ? 'tag-red' : h.trend === '看空' ? 'tag-green' : 'tag-blue'}`}>{h.trend}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {/* Report */}
                {(portReport || portLoading) && (
                    <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <div style={{ fontSize: 15, fontWeight: 600, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>💼 组合体检报告</div>
                        <div ref={portReportRef} className="markdown-body" style={{ flex: 1, overflowY: 'auto', padding: '16px 0', lineHeight: 1.75 }}>
                            <ReactMarkdown>{portReport || (portLoading ? '分析中...' : '')}</ReactMarkdown>
                            {portLoading && portReport && <span className="cursor-blink">▍</span>}
                        </div>
                    </div>
                )}
            </div>
        )
    }

    return (
        <div style={{ display: 'flex', maxWidth: 1400, margin: '0 auto', gap: 0 }}>
            {renderStockList()}
            {analyzeMode === 'single' ? renderSinglePanel() : renderPortfolioPanel()}
            {renderAddForm()}
        </div>
    )
}
