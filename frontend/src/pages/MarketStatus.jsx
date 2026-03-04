import { useState, useEffect, useRef } from 'react'
import {
    Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
    LineChart, Line, YAxis, Tooltip as RechartsTooltip
} from 'recharts'
import { Zap, Brain, Activity, TrendingUp, AlertTriangle, Play, Loader2, Wifi, WifiOff } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import useWebSocket from '../hooks/useWebSocket'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// 五个档位的颜色配置
const REGIME_COLORS = {
    1: '#ef4444', // 恐慌下跌 - 红
    2: '#f97316', // 弱势调整 - 橙
    3: '#f59e0b', // 震荡整理 - 黄
    4: '#84cc16', // 温和上涨 - 浅绿
    5: '#10b981'  // 强势上涨 - 绿
}

export default function MarketStatus() {
    const [mode, setMode] = useState('quant') // 'quant' | 'llm'
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [data, setData] = useState(null)
    const [llmReport, setLlmReport] = useState("")
    const { summary: wsSummary, status: wsStatus, lastUpdate: wsLastUpdate, isTrading } = useWebSocket()

    // 中断控制
    const abortControllerRef = useRef(null)

    // 初次加载量化数据
    useEffect(() => {
        fetchQuantData()
        return () => stopStream()
    }, [])

    const stopStream = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
        }
    }

    const fetchQuantData = async () => {
        setLoading(true)
        setError(null)
        try {
            const res = await fetch(`${API}/market/status`)
            if (!res.ok) throw new Error('网络请求失败')
            const json = await res.json()
            if (json.error) throw new Error(json.error)
            setData(json)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const startLLMAnalysis = async () => {
        if (loading) return
        setMode('llm')
        setLoading(true)
        setError(null)
        setLlmReport("")
        stopStream()

        abortControllerRef.current = new AbortController()

        try {
            const res = await fetch(`${API}/market/status/llm`, {
                signal: abortControllerRef.current.signal
            })
            if (!res.ok) throw new Error('流式请求失败')

            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ""

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })

                // SSE 事件以 \n\n 分隔
                const events = buffer.split('\n\n')
                buffer = events.pop() || "" // 最后一段可能不完整，留到下次

                for (const event of events) {
                    for (const line of event.split('\n')) {
                        if (!line.startsWith('data: ')) continue
                        const content = line.slice(6)
                        if (content === '[DONE]') break

                        // 尝试解析 JSON（quant_data）
                        if (content.startsWith('{')) {
                            try {
                                const parsed = JSON.parse(content)
                                if (parsed.type === 'quant_data') {
                                    setData(parsed.data)
                                    continue
                                }
                            } catch (e) {
                                // JSON 解析失败，忽略（不要当成 LLM 文本）
                                continue
                            }
                        }

                        // 普通 markdown 文本块
                        setLlmReport(prev => prev + content)
                    }
                }
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                setError(err.message)
            }
        } finally {
            setLoading(false)
            abortControllerRef.current = null
        }
    }

    // 将四维得分转换为 Radar 格式
    const radarData = data ? [
        { subject: '趋势 (Trend)', A: data.dimensions.trend, fullMark: 100 },
        { subject: '情绪 (Sentiment)', A: data.dimensions.sentiment, fullMark: 100 },
        { subject: '资金 (Capital)', A: data.dimensions.capital, fullMark: 100 },
        { subject: '波动 (Volatility)', A: data.dimensions.volatility, fullMark: 100 },
    ] : []

    const color = data ? REGIME_COLORS[data.regime.level] : 'var(--border)'

    return (
        <div style={{ maxWidth: 1200, margin: '0 auto' }} className="animate-fadein">
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                <div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Activity color="var(--accent-blue)" />
                        市场状态全景仪
                    </h1>
                    <div style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                        多维度量化监控，把握市场跳动节奏
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, fontSize: 12 }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: wsStatus === 'connected' ? '#10b981' : wsStatus === 'connecting' ? '#f59e0b' : '#ef4444', display: 'inline-block', boxShadow: wsStatus === 'connected' ? '0 0 6px #10b981' : 'none' }}></span>
                        <span style={{ color: 'var(--text-secondary)' }}>
                            {wsStatus === 'connected' ? `实时连接中` : wsStatus === 'connecting' ? '连接中...' : '未连接'}
                            {wsLastUpdate && ` · 更新于 ${wsLastUpdate}`}
                        </span>
                    </div>
                </div>

                {/* 模式切换 */}
                <div style={{ display: 'flex', background: 'var(--bg-card)', padding: 4, borderRadius: 8, border: '1px solid var(--border)' }}>
                    <button
                        className="btn"
                        style={{ background: mode === 'quant' ? 'var(--bg-secondary)' : 'transparent', color: mode === 'quant' ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                        onClick={() => { setMode('quant'); stopStream(); }}
                    >
                        <Zap size={16} color={mode === 'quant' ? 'var(--accent-gold)' : 'inherit'} />
                        纯量化速查
                    </button>
                    <button
                        className="btn"
                        style={{ background: mode === 'llm' ? 'var(--accent-blue)' : 'transparent', color: mode === 'llm' ? 'white' : 'var(--text-secondary)' }}
                        onClick={startLLMAnalysis}
                        disabled={loading && mode === 'llm'}
                    >
                        {loading && mode === 'llm' ? <Loader2 size={16} className="spinner" /> : <Brain size={16} />}
                        AI 深度分析
                    </button>
                </div>
            </div>

            {error && (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderLeft: '4px solid var(--accent-red)', padding: '12px 16px', marginBottom: 24, borderRadius: '0 8px 8px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
                    <AlertTriangle color="var(--accent-red)" size={20} />
                    {error}
                </div>
            )}

            {/* 实时市场概况 */}
            {wsSummary && (
                <div className="card animate-fadein" style={{ padding: '12px 20px', marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                    <div style={{ display: 'flex', gap: 20, alignItems: 'center', fontSize: 14 }}>
                        <span style={{ color: 'var(--text-secondary)' }}>全市场 <strong style={{ color: 'var(--text-primary)' }}>{wsSummary.total}</strong> 只</span>
                        <span style={{ color: 'var(--accent-red)' }}>▲ 上涨 <strong>{wsSummary.up_count}</strong></span>
                        <span style={{ color: 'var(--accent-green)' }}>▼ 下跌 <strong>{wsSummary.down_count}</strong></span>
                        <span style={{ color: 'var(--text-secondary)' }}>— 平盘 {wsSummary.flat_count}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 16, alignItems: 'center', fontSize: 13 }}>
                        <span style={{ background: 'rgba(239,68,68,0.15)', padding: '2px 8px', borderRadius: 4, color: 'var(--accent-red)', fontWeight: 600 }}>涨停 {wsSummary.limit_up}</span>
                        <span style={{ background: 'rgba(16,185,129,0.15)', padding: '2px 8px', borderRadius: 4, color: 'var(--accent-green)', fontWeight: 600 }}>跌停 {wsSummary.limit_down}</span>
                        <span style={{ color: wsSummary.avg_change > 0 ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 600 }}>
                            均涨幅 {wsSummary.avg_change > 0 ? '+' : ''}{wsSummary.avg_change}%
                        </span>
                    </div>
                </div>
            )}

            {!data && loading && mode === 'quant' && (
                <div className="skeleton" style={{ height: 400, width: '100%', borderRadius: 12 }}></div>
            )}

            {data && (
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(350px, 1fr) 1fr', gap: 24, marginBottom: 24 }}>

                    {/* 左侧：温度计 & 三大指数 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                        <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px', position: 'relative', overflow: 'hidden' }}>
                            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: color }}></div>

                            {/* 温度分 */}
                            <div style={{ fontSize: 72, fontWeight: 800, color: color, lineHeight: 1, textShadow: `0 0 40px ${color}40` }}>
                                {data.score}
                            </div>
                            <div style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)', marginTop: 12, marginBottom: 8 }}>
                                {data.regime.name}
                            </div>
                            <div style={{ fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.5, maxWidth: '80%' }}>
                                {data.regime.desc}
                            </div>
                        </div>

                        {/* 三大指数走势迷你图 */}
                        <div className="card" style={{ padding: '16px 20px' }}>
                            <h3 style={{ margin: '0 0 16px', fontSize: 14, color: 'var(--text-secondary)' }}>最近20个交易日走势追踪</h3>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                {Object.entries(data.charts || {}).map(([key, chartData]) => {
                                    const names = { sh: '上证指数', sz: '深证成指', hs300: '沪深300' };
                                    const latest = chartData[chartData.length - 1];
                                    const isUp = latest && latest.pct_chg > 0;
                                    return (
                                        <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 12, borderBottom: key !== 'hs300' ? '1px solid var(--border)' : 'none' }}>
                                            <div style={{ minWidth: 80 }}>
                                                <div style={{ fontSize: 14, fontWeight: 600 }}>{names[key]}</div>
                                                {latest && (
                                                    <div style={{ fontSize: 12, color: isUp ? 'var(--accent-red)' : 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        {isUp ? <TrendingUp size={12} /> : <TrendingUp size={12} style={{ transform: 'rotate(180deg)' }} />}
                                                        {latest.pct_chg.toFixed(2)}%
                                                    </div>
                                                )}
                                            </div>
                                            <div style={{ width: 120, height: 40 }}>
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <LineChart data={chartData}>
                                                        <YAxis domain={['auto', 'auto']} hide />
                                                        <Line type="monotone" dataKey="close" stroke={isUp ? 'var(--accent-red)' : 'var(--accent-green)'} strokeWidth={2} dot={false} isAnimationActive={false} />
                                                        <RechartsTooltip
                                                            contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12, padding: 8 }}
                                                            formatter={(val) => val.toFixed(2)}
                                                            labelFormatter={() => ''}
                                                        />
                                                    </LineChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    </div>

                    {/* 右侧：雷达图 & 推荐策略 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                        <div className="card" style={{ display: 'flex', padding: 0, overflow: 'hidden' }}>
                            <div style={{ flex: 1, padding: 24, borderRight: '1px solid var(--border)' }}>
                                <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>四维市场解析</h3>
                                <div style={{ height: 250 }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                                            <PolarGrid stroke="var(--border)" />
                                            <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                                            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                                            <Radar name="市场得分" dataKey="A" stroke={color} fill={color} fillOpacity={0.4} />
                                            <RechartsTooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} />
                                        </RadarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div style={{ width: 280, padding: 24, background: 'var(--bg-secondary)' }}>
                                <h3 style={{ margin: '0 0 16px', fontSize: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <Play size={16} color="var(--accent-gold)" />
                                    当前推荐策略模板
                                </h3>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                    {data.recommendations.map((tpl, i) => (
                                        <div key={tpl.id} style={{ background: 'var(--bg-card)', padding: '12px', borderRadius: 8, border: `1px solid ${i === 0 ? 'var(--accent-gold)' : 'var(--border)'}`, position: 'relative' }}>
                                            {i === 0 && <div style={{ position: 'absolute', top: -8, right: 12, background: 'var(--accent-gold)', color: '#000', fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 'bold' }}>最优匹配</div>}
                                            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{tpl.name}</div>
                                            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{tpl.description}</div>
                                            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'flex-end' }}>
                                                匹配度: <span style={{ color: 'var(--accent-gold)', marginLeft: 4, fontWeight: 'bold' }}>{tpl.match_score}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* AI 分析区 */}
            {mode === 'llm' && (
                <div className="card" style={{ padding: 24, border: '1px solid var(--accent-blue)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
                        <Brain color="var(--accent-blue)" />
                        <h2 style={{ fontSize: 18, margin: 0 }}>AI 深度宏观研判</h2>
                        {loading && <div className="tag tag-blue"><Loader2 size={12} className="spinner" style={{ display: 'inline-block', marginRight: 4, verticalAlign: 'middle' }} />分析中...</div>}
                    </div>

                    <div className="markdown-body" style={{ minHeight: 200, fontSize: 15, lineHeight: 1.7 }}>
                        {llmReport === "" && loading ? (
                            <div style={{ color: 'var(--text-secondary)' }}>正在拉取全市场新闻快讯并生成报告，请稍候...</div>
                        ) : (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {llmReport + (loading ? ' █' : '')}
                            </ReactMarkdown>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
