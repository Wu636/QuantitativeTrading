import { useState, useRef, useEffect } from 'react'
import { Brain, Send, AlertTriangle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const API = ''

export default function Analyst() {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [meta, setMeta] = useState(null)
  const [report, setReport] = useState('')
  const [configOk, setConfigOk] = useState(null)
  const reportRef = useRef(null)
  const abortRef = useRef(null)

  // 检查 LLM 配置
  useEffect(() => {
    fetch(`${API}/api/analyst/config-check`)
      .then(r => r.json())
      .then(d => setConfigOk(d))
      .catch(() => setConfigOk({ ready: false }))
  }, [])

  // 自动滚到底部
  useEffect(() => {
    if (reportRef.current) {
      reportRef.current.scrollTop = reportRef.current.scrollHeight
    }
  }, [report])

  const handleAnalyze = async () => {
    const trimmed = code.trim()
    if (!trimmed) return
    setLoading(true)
    setStatus('正在连接...')
    setMeta(null)
    setReport('')

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const resp = await fetch(`${API}/api/analyst/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: trimmed }),
        signal: ctrl.signal,
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // 解析 SSE
        const lines = buffer.split('\n')
        buffer = lines.pop() // 保留不完整的行

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7)
          } else if (line.startsWith('data: ') && eventType === 'event') {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'status') {
                setStatus(data.message)
              } else if (data.type === 'meta') {
                setMeta(data)
                setStatus('AI 正在撰写分析报告...')
              } else if (data.type === 'token') {
                setReport(prev => prev + data.content)
              } else if (data.type === 'done') {
                setStatus('')
              } else if (data.type === 'error') {
                setStatus(`❌ ${data.message}`)
              }
            } catch { /* 忽略非 JSON 行 */ }
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setStatus(`❌ 请求失败: ${e.message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      setLoading(false)
      setStatus('已停止')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !loading) handleAnalyze()
  }

  // ───────── 渲染 ─────────

  return (
    <div className="animate-fadein" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Brain size={26} color="var(--accent-gold)" />
          AI 金融分析师
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 6 }}>
          输入股票代码，AI 将基于实时行情数据生成专业分析报告
        </p>
      </div>

      {/* 配置检查提示 */}
      {configOk && !configOk.ready && (
        <div className="card" style={{
          marginBottom: 16, padding: '14px 18px',
          borderColor: 'var(--accent-gold)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <AlertTriangle size={18} color="var(--accent-gold)" />
          <div style={{ fontSize: 13 }}>
            <strong>LLM 未配置：</strong>请在项目根目录创建 <code>.env</code> 文件，设置
            <code> LLM_API_KEY</code>、<code>LLM_BASE_URL</code>、<code>LLM_MODEL</code>
            {!configOk.has_api_key && <span style={{ color: 'var(--accent-red)' }}> (缺少 API Key)</span>}
            {!configOk.has_base_url && <span style={{ color: 'var(--accent-red)' }}> (缺少 Base URL)</span>}
          </div>
        </div>
      )}
      {configOk && configOk.ready && (
        <div style={{
          marginBottom: 16, padding: '8px 14px', borderRadius: 8,
          background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)',
          fontSize: 12, color: 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: 8,
        }}>
          ✅ LLM 已配置&ensp;|&ensp;模型: {configOk.model || '默认'}
        </div>
      )}

      {/* 输入栏 */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', gap: 12, alignItems: 'center', padding: '14px 18px' }}>
        <input
          className="input-field"
          style={{ maxWidth: 260 }}
          placeholder="输入股票代码，如 000001"
          value={code}
          onChange={e => setCode(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        {!loading ? (
          <button className="btn btn-primary" onClick={handleAnalyze} disabled={!code.trim() || (configOk && !configOk.ready)}>
            <Send size={15} /> 开始分析
          </button>
        ) : (
          <button className="btn btn-outline" onClick={handleStop} style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)' }}>
            停止
          </button>
        )}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
            <div className="spinner" />
            {status}
          </div>
        )}
        {!loading && status && (
          <span style={{ fontSize: 13, color: status.startsWith('❌') ? 'var(--accent-red)' : 'var(--text-secondary)' }}>
            {status}
          </span>
        )}
      </div>

      {/* 数据指标卡片 */}
      {meta && <MetaCards meta={meta} />}

      {/* LLM 分析报告 */}
      {(report || loading) && (
        <div className="card" style={{ marginTop: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Brain size={17} color="var(--accent-blue)" />
            AI 分析报告
            {meta?.name && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>— {meta.name} ({meta.code})</span>}
          </div>
          <div
            ref={reportRef}
            className="markdown-body"
            style={{
              maxHeight: 600, overflowY: 'auto', padding: '0 4px',
              lineHeight: 1.75, fontSize: 14,
            }}
          >
            <ReactMarkdown>{report || (loading ? '等待 AI 输出...' : '')}</ReactMarkdown>
            {loading && report && <span className="cursor-blink">▍</span>}
          </div>
        </div>
      )}
    </div>
  )
}


/* ─── 数据指标卡片区 ─── */
function MetaCards({ meta }) {
  const price = meta.price
  const changePct = meta.change_pct
  const valuation = meta.valuation || {}
  const market = meta.market || {}
  const indicators = meta.indicators || {}
  const sr = meta.support_resistance || {}
  const trend = meta.trend
  const techScore = meta.tech_score

  const supports = (sr.levels || []).filter(l => l.kind === 'support' && l.price < (sr.current_price || 0)).sort((a, b) => b.price - a.price).slice(0, 3)
  const resistances = (sr.levels || []).filter(l => l.kind === 'resistance' && l.price > (sr.current_price || 0)).sort((a, b) => a.price - b.price).slice(0, 3)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
      {/* 行情概览 */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>行情概览</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ fontSize: 22, fontWeight: 700 }}>{price ?? '--'}</span>
          {changePct != null && (
            <span className={changePct >= 0 ? 'metric-up' : 'metric-down'} style={{ fontSize: 14, fontWeight: 600 }}>
              {changePct >= 0 ? '+' : ''}{changePct?.toFixed(2)}%
            </span>
          )}
        </div>
        <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {trend && <span className={`tag ${trend === '看多' ? 'tag-green' : trend === '看空' ? 'tag-red' : 'tag-blue'}`}>{trend}</span>}
          {techScore != null && <span className="tag tag-gold">技术评分 {techScore}</span>}
        </div>
      </div>

      {/* 估值指标 */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>估值指标</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
          <Metric label="PE" value={valuation.pe} />
          <Metric label="PB" value={valuation.pb} />
          <Metric label="ROE" value={valuation.roe} suffix="%" />
          <Metric label="换手率" value={market.turnover} suffix="%" />
          <Metric label="量比" value={market.volume_ratio} />
          <Metric label="市值" value={market.cap ? `${(market.cap / 1e8).toFixed(0)}亿` : null} />
        </div>
      </div>

      {/* 技术指标 */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>技术指标</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
          <Metric label="RSI" value={indicators.rsi} />
          <Metric label="MACD" value={indicators.macd} />
          <Metric label="KDJ-K" value={indicators.kdj_k} />
          <Metric label="KDJ-D" value={indicators.kdj_d} />
          <Metric label="ATR" value={indicators.atr} />
          <Metric label="BOLL中轨" value={indicators.boll_mid} />
        </div>
      </div>

      {/* 压力 / 支撑位 */}
      <div className="card" style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>关键价位</div>
        <div style={{ fontSize: 13 }}>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: 'var(--accent-red)', fontWeight: 600, marginRight: 6 }}>▲ 压力位</span>
            {resistances.length ? resistances.map((r, i) => (
              <span key={i} style={{ marginRight: 8 }}>{r.price} <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>({r.name})</span></span>
            )) : <span style={{ color: 'var(--text-secondary)' }}>--</span>}
          </div>
          <div>
            <span style={{ color: 'var(--accent-green)', fontWeight: 600, marginRight: 6 }}>▼ 支撑位</span>
            {supports.length ? supports.map((s, i) => (
              <span key={i} style={{ marginRight: 8 }}>{s.price} <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>({s.name})</span></span>
            )) : <span style={{ color: 'var(--text-secondary)' }}>--</span>}
          </div>
        </div>
      </div>
    </div>
  )
}


/* ─── 小指标组件 ─── */
function Metric({ label, value, suffix = '' }) {
  const display = value != null && value !== '' ? (typeof value === 'number' ? value.toFixed(2) : value) : '--'
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{display}{value != null && suffix}</span>
    </div>
  )
}
