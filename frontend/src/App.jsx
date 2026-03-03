import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { TrendingUp, Search, BarChart2, Activity, Brain } from 'lucide-react'
import Backtest from './pages/Backtest'
import Compare from './pages/Compare'
import Picker from './pages/Picker'
import WalkForward from './pages/WalkForward'
import Analyst from './pages/Analyst'
import './index.css'

function Layout({ children }) {
  const navItems = [
    { to: '/', label: '单股回测', Icon: TrendingUp },
    { to: '/compare', label: '策略对比', Icon: BarChart2 },
    { to: '/picker', label: '选股中心', Icon: Search },
    { to: '/walk-forward', label: 'Walk-Forward', Icon: Activity },
    { to: '/analyst', label: 'AI分析', Icon: Brain },
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div style={{
        width: 220,
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 12px',
        position: 'fixed',
        top: 0, left: 0, bottom: 0,
      }}>
        {/* Logo */}
        <div style={{ padding: '0 8px 24px', borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent-gold)', letterSpacing: 1 }}>
            📈 量化系统
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
            A股量化交易平台
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {navItems.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '12px 8px 0', borderTop: '1px solid var(--border)' }}>
          <div>后端: localhost:8000</div>
          <div style={{ marginTop: 4 }}>数据: akshare</div>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, marginLeft: 220, padding: 28, minHeight: '100vh' }}>
        {children}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Backtest />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/picker" element={<Picker />} />
          <Route path="/walk-forward" element={<WalkForward />} />
          <Route path="/analyst" element={<Analyst />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
