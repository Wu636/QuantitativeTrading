import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace('http', 'ws') + '/ws/market'

/**
 * 实时行情 WebSocket Hook
 *
 * @returns {{ snapshot, timing, summary, status, lastUpdate, isTrading }}
 */
export default function useWebSocket() {
    const [summary, setSummary] = useState(null)
    const [timing, setTiming] = useState(null)
    const [status, setStatus] = useState('disconnected')
    const [lastUpdate, setLastUpdate] = useState(null)
    const [isTrading, setIsTrading] = useState(false)
    const wsRef = useRef(null)
    const reconnectTimer = useRef(null)
    const retryCount = useRef(0)

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return
        setStatus('connecting')

        const ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
            setStatus('connected')
            retryCount.current = 0
            console.log('🟢 WebSocket 已连接')
        }

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data)
                if (msg.type === 'realtime_update') {
                    setSummary(msg.summary)
                    setTiming(msg.timing)
                    setLastUpdate(msg.timestamp)
                    setIsTrading(true)
                } else if (msg.type === 'market_snapshot') {
                    // 兼容旧格式
                    setLastUpdate(msg.timestamp)
                    setIsTrading(true)
                } else if (msg.type === 'heartbeat') {
                    setIsTrading(msg.trading)
                    setLastUpdate(msg.timestamp)
                }
            } catch (e) {
                // ignore
            }
        }

        ws.onclose = () => {
            setStatus('disconnected')
            wsRef.current = null
            const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000)
            retryCount.current++
            console.log(`🔴 WebSocket 断开，${delay / 1000}s 后重连...`)
            reconnectTimer.current = setTimeout(connect, delay)
        }

        ws.onerror = () => {
            ws.close()
        }
    }, [])

    useEffect(() => {
        connect()
        return () => {
            clearTimeout(reconnectTimer.current)
            wsRef.current?.close()
        }
    }, [connect])

    return { summary, timing, status, lastUpdate, isTrading }
}
