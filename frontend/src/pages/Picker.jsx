import { useState, useEffect } from 'react'
import { Search, Save, Trash2, Plus, Info } from 'lucide-react'

const API = ''

export default function Picker() {
    // === 筛选参数状态 ===
    const [topN, setTopN] = useState(20)
    const [maxPe, setMaxPe] = useState(50)
    const [minPe, setMinPe] = useState(0)
    const [maxPb, setMaxPb] = useState(10)
    const [minMarketCap, setMinMarketCap] = useState(50)
    const [maxMarketCap, setMaxMarketCap] = useState(500)
    const [minPrice, setMinPrice] = useState(2)
    const [maxPrice, setMaxPrice] = useState(500)
    const [minTurnover, setMinTurnover] = useState(0.3)
    const [minRoe, setMinRoe] = useState(0)
    const [minVolumeRatio, setMinVolumeRatio] = useState(0)
    const [maxVolumeRatio, setMaxVolumeRatio] = useState(null)
    const [industryPbAware, setIndustryPbAware] = useState(false)
    const [minMomentum, setMinMomentum] = useState(null)
    
    // === 权重参数状态（7 因子）===
    const [weights, setWeights] = useState({
        value: 0.25,
        momentum: 0.25,
        quality: 0.20,
        liquidity: 0.10,
        size: 0.20,
        capital_flow: 0.0,
        roe: 0.0,
    })

    // === 其他状态 ===
    const [templates, setTemplates] = useState([])
    const [activeTemplateId, setActiveTemplateId] = useState(null)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    
    // === 弹窗状态 ===
    const [showSaveModal, setShowSaveModal] = useState(false)
    const [newTemplateName, setNewTemplateName] = useState('')
    const [newTemplateDesc, setNewTemplateDesc] = useState('')

    // 获取模板列表
    useEffect(() => {
        fetchTemplates()
    }, [])

    async function fetchTemplates() {
        try {
            const res = await fetch(`${API}/api/stock-picker/templates`)
            if (res.ok) {
                const data = await res.json()
                setTemplates(data.templates)
                // 默认选中第一个
                if (data.templates.length > 0 && !activeTemplateId) {
                    applyTemplate(data.templates[0])
                }
            }
        } catch (e) {
            console.error("加载模板失败", e)
        }
    }

    function applyTemplate(tmpl) {
        setActiveTemplateId(tmpl.id)
        const f = tmpl.filters || {}
        setMaxPe(f.max_pe ?? 50)
        setMinPe(f.min_pe ?? 0)
        setMaxPb(f.max_pb ?? 10)
        setMinMarketCap(f.min_market_cap ?? 50)
        setMaxMarketCap(f.max_market_cap ?? 500)
        setMinPrice(f.min_price ?? 2)
        setMaxPrice(f.max_price ?? 500)
        setMinTurnover(f.min_turnover ?? 0.3)
        setMinRoe(f.min_roe ?? 0)
        setMinVolumeRatio(f.min_volume_ratio ?? 0)
        setMaxVolumeRatio(f.max_volume_ratio ?? null)
        setIndustryPbAware(f.industry_pb_aware ?? false)
        setMinMomentum(f.min_momentum ?? null)
        setTopN(tmpl.top_n ?? 20)
        if (tmpl.weights) {
            setWeights(w => ({
                value: 0, momentum: 0, quality: 0, liquidity: 0, size: 0, capital_flow: 0, roe: 0,
                ...tmpl.weights
            }))
        }
    }

    async function deleteTemplate(id, e) {
        e.stopPropagation()
        if (!confirm('确定要删除该模板吗？')) return
        try {
            const res = await fetch(`${API}/api/stock-picker/templates/${id}`, { method: 'DELETE' })
            if (res.ok) {
                if (activeTemplateId === id) setActiveTemplateId(null)
                fetchTemplates()
            } else {
                alert((await res.json()).detail || '删除失败')
            }
        } catch (e) {
            alert('删除失败: ' + e.message)
        }
    }

    async function saveCustomTemplate() {
        if (!newTemplateName.trim()) {
            alert("请输入模板名称")
            return
        }
        try {
            const res = await fetch(`${API}/api/stock-picker/templates`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: newTemplateName,
                    description: newTemplateDesc,
                    top_n: topN,
                    filters: {
                        max_pe: maxPe, min_pe: minPe, max_pb: maxPb,
                        min_market_cap: minMarketCap, max_market_cap: maxMarketCap,
                        min_price: minPrice, max_price: maxPrice, min_turnover: minTurnover,
                        min_roe: minRoe || null, min_volume_ratio: minVolumeRatio || null,
                        max_volume_ratio: maxVolumeRatio || null,
                        industry_pb_aware: industryPbAware,
                        min_momentum: minMomentum || null,
                    },
                    weights: weights
                })
            })
            if (res.ok) {
                setShowSaveModal(false)
                setNewTemplateName('')
                setNewTemplateDesc('')
                fetchTemplates()
                const data = await res.json()
                if (data.template) {
                     setActiveTemplateId(data.template.id)
                }
            } else {
                alert((await res.json()).detail || '保存失败')
            }
        } catch (e) {
             alert('保存失败: ' + e.message)
        }
    }

    async function run() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const res = await fetch(`${API}/api/stock-picker`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    top_n: topN,
                    max_pe: maxPe,
                    min_pe: minPe,
                    max_pb: maxPb,
                    min_market_cap: minMarketCap * 1e8,
                    max_market_cap: maxMarketCap ? maxMarketCap * 1e8 : null,
                    min_price: minPrice,
                    max_price: maxPrice,
                    min_turnover: minTurnover,
                    min_roe: minRoe || null,
                    min_volume_ratio: minVolumeRatio || null,
                    max_volume_ratio: maxVolumeRatio || null,
                    industry_pb_aware: industryPbAware,
                    min_momentum: minMomentum || null,
                    weights: weights,
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

    function scoreColor(score) {
        if (score >= 70) return 'var(--accent-green)'
        if (score >= 50) return 'var(--accent-gold)'
        return 'var(--text-secondary)'
    }

    function pctStr(v) {
        if (v === undefined || v === null || isNaN(v)) return '—'
        return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
    }

    function capStr(v) {
        if (!v) return '—'
        if (v >= 1e12) return `${(v / 1e12).toFixed(1)}万亿`
        if (v >= 1e8) return `${(v / 1e8).toFixed(0)}亿`
        return v.toLocaleString()
    }

    return (
        <div className="animate-fadein" style={{ position: 'relative' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>选股中心</h1>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                        选择策略模板，自动填入参数并筛选全市场个股
                    </p>
                </div>
            </div>

            {/* 1. 模板选择栏 */}
            <div style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>1. 选择选股模板</h3>
                <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
                    {templates.map(tmpl => (
                        <div 
                            key={tmpl.id} 
                            onClick={() => applyTemplate(tmpl)}
                            style={{ 
                                minWidth: 200, padding: '14px 16px', borderRadius: 10, cursor: 'pointer',
                                border: `1px solid ${activeTemplateId === tmpl.id ? 'var(--accent-blue)' : 'var(--border)'}`,
                                background: activeTemplateId === tmpl.id ? 'rgba(59, 130, 246, 0.05)' : 'var(--bg-card)',
                                transition: 'all 0.2s', position: 'relative'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                                <span style={{ fontWeight: 600, color: activeTemplateId === tmpl.id ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                                    {tmpl.name}
                                </span>
                                {!tmpl.builtin && (
                                    <Trash2 size={14} style={{ color: 'var(--accent-red)', opacity: 0.7 }} 
                                        onClick={(e) => deleteTemplate(tmpl.id, e)} />
                                )}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                {tmpl.description || '自定义模板'}
                            </div>
                        </div>
                    ))}
                    
                    <div 
                        onClick={() => { setActiveTemplateId(null); setShowSaveModal(true) }}
                        style={{ 
                            minWidth: 160, padding: 16, borderRadius: 10, cursor: 'pointer',
                            border: '1px dashed var(--border)', background: 'transparent',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-secondary)', transition: 'all 0.2s'
                        }}
                    >
                        <Plus size={20} style={{ marginBottom: 8 }} />
                        <span style={{ fontSize: 13, fontWeight: 500 }}>保存为新模板</span>
                    </div>
                </div>
            </div>

            {/* 2. 筛选参数和权重配置 */}
            <div className="card" style={{ marginBottom: 24, padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>2. 调整选股规则与权重</h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
                        <Info size={14}/> 修改参数后可保存为新模板
                    </div>
                </div>
                
                {/* 基础筛选条件 */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px 20px', marginBottom: 24 }}>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>市盈率下限 (PE)</label><input className="input-field" type="number" step="0.1" value={minPe} onChange={e => { setMinPe(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>市盈率上限 (PE)</label><input className="input-field" type="number" step="0.1" value={maxPe} onChange={e => { setMaxPe(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>市净率上限 (PB)</label><input className="input-field" type="number" step="0.1" value={maxPb} onChange={e => { setMaxPb(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低换手率 (%)</label><input className="input-field" type="number" step="0.1" value={minTurnover} onChange={e => { setMinTurnover(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>返回数量 Top N</label><input className="input-field" type="number" value={topN} onChange={e => { setTopN(parseInt(e.target.value) || 20); setActiveTemplateId(null) }} /></div>
                    
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低市值 (亿元)</label><input className="input-field" type="number" value={minMarketCap} onChange={e => { setMinMarketCap(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最高市值 (亿元)</label><input className="input-field" type="number" value={maxMarketCap || ''} placeholder="无限制" onChange={e => { setMaxMarketCap(parseFloat(e.target.value) || null); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低股价 (元)</label><input className="input-field" type="number" step="0.1" value={minPrice} onChange={e => { setMinPrice(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最高股价 (元)</label><input className="input-field" type="number" step="0.1" value={maxPrice} onChange={e => { setMaxPrice(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                </div>

                {/* 进阶筛选条件 */}
                <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>进阶条件（策略增强）</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px 20px', marginBottom: 16 }}>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低 ROE (%)</label><input className="input-field" type="number" step="1" value={minRoe} onChange={e => { setMinRoe(parseFloat(e.target.value) || 0); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低量比</label><input className="input-field" type="number" step="0.1" value={minVolumeRatio || ''} placeholder="不限" onChange={e => { setMinVolumeRatio(parseFloat(e.target.value) || null); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最高量比（缩量用）</label><input className="input-field" type="number" step="0.1" value={maxVolumeRatio || ''} placeholder="不限" onChange={e => { setMaxVolumeRatio(parseFloat(e.target.value) || null); setActiveTemplateId(null) }} /></div>
                    <div><label style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>最低 60日涨幅 (%)</label><input className="input-field" type="number" step="1" value={minMomentum ?? ''} placeholder="不限" onChange={e => { setMinMomentum(parseFloat(e.target.value) || null); setActiveTemplateId(null) }} /></div>
                    <div style={{ display: 'flex', alignItems: 'end' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-primary)', cursor: 'pointer', padding: '8px 0' }}>
                            <input type="checkbox" checked={industryPbAware} onChange={e => { setIndustryPbAware(e.target.checked); setActiveTemplateId(null) }} style={{ accentColor: 'var(--accent-blue)' }} />
                            分行业 PB 阈值
                            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>（银行/地产等）</span>
                        </label>
                    </div>
                </div>

                <hr style={{ borderTop: '1px solid var(--border)', borderBottom: 'none', margin: '0 0 20px 0', opacity: 0.5 }}/>
                
                {/* 因子权重滑块 - 7因子 */}
                <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 16 }}>多因子打分权重配置（7 因子）</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24, marginBottom: 20 }}>
                    {Object.entries({ 'value': '💎 价值', 'momentum': '🚀 动量', 'quality': '🏅 质量', 'liquidity': '💧 流动性', 'size': '📐 市值', 'capital_flow': '🔥 资金流', 'roe': '📈 ROE' }).map(([key, label]) => (
                        <div key={key}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 8 }}>
                                <span style={{ color: 'var(--text-primary)' }}>{label}</span>
                                <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>{(weights[key] * 100).toFixed(0)}%</span>
                            </div>
                            <input 
                                type="range" min="0" max="1" step="0.05"
                                value={weights[key]}
                                onChange={(e) => {
                                    setWeights(w => ({ ...w, [key]: parseFloat(e.target.value) }))
                                    setActiveTemplateId(null)
                                }}
                                style={{ width: '100%', accentColor: 'var(--accent-blue)' }}
                            />
                        </div>
                    ))}
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: 10 }}>
                    <button className="btn btn-primary" onClick={run} disabled={loading} style={{ height: 42, padding: '0 32px', fontSize: 15, borderRadius: 8 }}>
                        {loading ? <span className="spinner" style={{ width: 16, height: 16 }} /> : <Search size={18} />}
                        {loading ? '正在全网跨因子测算…' : '执行选股'}
                    </button>
                </div>
            </div>

            {/* 保存模板弹窗 */}
            {showSaveModal && (
                <div style={{
                    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, minHeight: '100vh',
                    background: 'rgba(0,0,0,0.7)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <div className="card animate-fadein" style={{ width: 400, transform: 'translateY(-100px)' }}>
                        <h3 style={{ marginTop: 0, marginBottom: 20, fontSize: 18, borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>保存自定义模板</h3>
                        
                        <div style={{ marginBottom: 16 }}>
                            <label style={{ display: 'block', fontSize: 13, marginBottom: 8, color: 'var(--text-secondary)' }}>模板名称 (带个图标如🚀更好看)</label>
                            <input className="input-field" value={newTemplateName} onChange={e => setNewTemplateName(e.target.value)} placeholder="如：🚀 短线强动量"/>
                        </div>
                        
                        <div style={{ marginBottom: 24 }}>
                            <label style={{ display: 'block', fontSize: 13, marginBottom: 8, color: 'var(--text-secondary)' }}>一句话描述</label>
                            <input className="input-field" value={newTemplateDesc} onChange={e => setNewTemplateDesc(e.target.value)} placeholder="如：适合持仓3-5天的量价突破票"/>
                        </div>
                        
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                            <button className="btn btn-outline" onClick={() => setShowSaveModal(false)}>取消</button>
                            <button className="btn btn-primary" onClick={saveCustomTemplate}><Save size={16}/>确认保存</button>
                        </div>
                    </div>
                </div>
            )}

            {/* 列表渲染... */}
            {error && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '12px 16px', marginBottom: 20, color: 'var(--accent-red)', fontSize: 14 }}>
                    ❌ {error}
                </div>
            )}

            {loading && (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-secondary)' }}>
                    <div className="spinner" style={{ width: 36, height: 36, margin: '0 auto 16px' }} />
                    <div>正在扫描全市场股票，获取数据约需 30 秒…</div>
                </div>
            )}

            {result && !loading && (
                <>
                    <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontSize: 16, fontWeight: 600 }}>选股结果 Top {result.total}</span>
                        <span className="tag tag-gold">多因子排名</span>
                    </div>

                    <div className="card">
                        <div style={{ overflowX: 'auto' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>代码</th>
                                        <th>名称</th>
                                        <th>最新价</th>
                                        <th>涨跌幅</th>
                                        <th>PE</th>
                                        <th>PB</th>
                                        <th>总市值</th>
                                        <th>换手率</th>
                                        <th>量比</th>
                                        <th style={{ color: 'var(--accent-blue)' }}>价值</th>
                                        <th style={{ color: 'var(--accent-green)' }}>动量</th>
                                        <th style={{ color: 'var(--accent-gold)' }}>质量</th>
                                        <th style={{ color: '#a78bfa' }}>流动</th>
                                        <th style={{ color: '#06b6d4' }}>市值</th>
                                        <th style={{ color: '#f97316' }}>资金</th>
                                        <th style={{ color: '#10b981' }}>ROE</th>
                                        <th style={{ fontWeight: 700 }}>总分</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {result.stocks.map((s, i) => (
                                        <tr key={i}>
                                            <td style={{ fontWeight: 600, color: i < 3 ? 'var(--accent-gold)' : 'var(--text-secondary)' }}>{i + 1}</td>
                                            <td><span className="tag tag-blue">{s['代码']}</span></td>
                                            <td style={{ fontWeight: 500 }}>{s['名称']}</td>
                                            <td>¥{s['最新价']?.toFixed(2)}</td>
                                            <td style={{ color: s['涨跌幅'] > 0 ? 'var(--accent-green)' : s['涨跌幅'] < 0 ? 'var(--accent-red)' : 'var(--text-secondary)' }}>{pctStr(s['涨跌幅'])}</td>
                                            <td>{s['市盈率-动态']?.toFixed(1)}</td>
                                            <td>{s['市净率']?.toFixed(2)}</td>
                                            <td style={{ color: 'var(--text-secondary)' }}>{capStr(s['总市值'])}</td>
                                            <td>{s['换手率']?.toFixed(2)}%</td>
                                            <td>{s['量比']?.toFixed(2) ?? '—'}</td>
                                            <td style={{ color: scoreColor(s.factor_value) }}>{s.factor_value?.toFixed(0)}</td>
                                            <td style={{ color: scoreColor(s.factor_momentum) }}>{s.factor_momentum?.toFixed(0)}</td>
                                            <td style={{ color: scoreColor(s.factor_quality) }}>{s.factor_quality?.toFixed(0)}</td>
                                            <td style={{ color: scoreColor(s.factor_liquidity) }}>{s.factor_liquidity?.toFixed(0)}</td>
                                            <td style={{ color: scoreColor(s.factor_size) }}>{s.factor_size?.toFixed(0)}</td>
                                            <td style={{ color: scoreColor(s.factor_capital_flow) }}>{s.factor_capital_flow?.toFixed(0) ?? '—'}</td>
                                            <td style={{ color: scoreColor(s.factor_roe) }}>{s.factor_roe?.toFixed(0) ?? '—'}</td>
                                            <td style={{ fontWeight: 700, fontSize: 15, color: scoreColor(s.total_score) }}>{s.total_score?.toFixed(1)}</td>
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

