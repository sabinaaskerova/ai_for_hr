import { useState, useEffect } from 'react'
import { BarChart3, Loader2, TrendingUp, Target, Link2, Zap } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
} from 'recharts'
import clsx from 'clsx'
import DepartmentHeatmap from '../components/DepartmentHeatmap'
import { getDashboard, getTrends, getDepartments } from '../api/client'

const QUARTERS = ['', '2024-Q1', '2024-Q2', '2024-Q3', '2024-Q4', '2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4']

function MetricCard({ icon: Icon, label, value, unit = '', color = 'navy' }) {
  const colors = {
    navy: 'bg-navy-700 text-white',
    amber: 'bg-amber-500 text-white',
    emerald: 'bg-emerald-500 text-white',
    purple: 'bg-purple-600 text-white',
  }
  return (
    <div className="card flex items-center gap-4">
      <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0', colors[color])}>
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-900">
          {typeof value === 'number' ? value.toFixed(2) : '—'}
          <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>
        </div>
        <div className="text-sm text-gray-500">{label}</div>
      </div>
    </div>
  )
}

const BAR_COLORS = ['#1e3a5f', '#254c90', '#3360ab', '#5580c2', '#88a9d9', '#b9cceb', '#dce6f5', '#f0f4fa']

export default function Analytics() {
  const [quarter, setQuarter] = useState('')
  const [dashboard, setDashboard] = useState(null)
  const [trends, setTrends] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async (q) => {
    setLoading(true)
    setError(null)
    try {
      const [dash, tr] = await Promise.all([getDashboard(q || undefined), getTrends()])
      setDashboard(dash)
      setTrends(tr)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(quarter) }, [quarter])

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-96">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-navy-600 mx-auto mb-3" />
          <div className="text-gray-500">Загрузка аналитики...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-xl px-6 py-4 text-red-700">{error}</div>
      </div>
    )
  }

  const depts = dashboard?.departments ?? []
  const trendData = (trends?.trends ?? []).map((t) => ({
    ...t,
    label: t.quarter,
    smart: t.avg_smart_index,
    strategic: parseFloat((t.strategic_link_ratio * 100).toFixed(1)),
    impact: parseFloat((t.impact_goal_ratio * 100).toFixed(1)),
  }))

  const barData = [...depts]
    .sort((a, b) => b.avg_smart_index - a.avg_smart_index)
    .map((d) => ({
      name: d.department_name.split(' ')[0],
      fullName: d.department_name,
      smart: parseFloat((d.avg_smart_index ?? 0).toFixed(2)),
      maturity: parseFloat((d.maturity_index ?? 0).toFixed(2)),
    }))

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    const dept = depts.find((d) => d.department_name.startsWith(label))
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
        <div className="font-semibold text-gray-800 mb-1">{dept?.department_name ?? label}</div>
        {payload.map((p) => (
          <div key={p.dataKey} style={{ color: p.color }}>
            {p.name}: {p.value}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-navy-700 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Аналитика</h1>
            <p className="text-gray-500 text-sm">Дашборд качества целеполагания по подразделениям</p>
          </div>
        </div>
        <select
          value={quarter}
          onChange={(e) => setQuarter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
        >
          <option value="">Все кварталы</option>
          {QUARTERS.filter(Boolean).map((q) => <option key={q}>{q}</option>)}
        </select>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <MetricCard icon={Target} label="Средний SMART-индекс" value={dashboard?.overall_smart_index} unit="/5.0" color="navy" />
        <MetricCard icon={Link2} label="Стратегически связанных целей" value={dashboard ? dashboard.strategic_link_ratio * 100 : null} unit="%" color="purple" />
        <MetricCard icon={Zap} label="Impact-based целей" value={dashboard ? dashboard.impact_goal_ratio * 100 : null} unit="%" color="amber" />
        <MetricCard icon={TrendingUp} label="Maturity Index" value={dashboard?.maturity_index} unit="/5.0" color="emerald" />
      </div>

      {/* Insights */}
      {dashboard && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="card bg-emerald-50 border-emerald-100">
            <div className="text-xs font-semibold text-emerald-600 uppercase mb-1">Лучший департамент</div>
            <div className="font-semibold text-emerald-800 text-sm">{dashboard.top_department}</div>
          </div>
          <div className="card bg-red-50 border-red-100">
            <div className="text-xs font-semibold text-red-500 uppercase mb-1">Требует внимания</div>
            <div className="font-semibold text-red-700 text-sm">{dashboard.bottom_department}</div>
          </div>
          <div className="card bg-amber-50 border-amber-100">
            <div className="text-xs font-semibold text-amber-600 uppercase mb-1">Слабейший критерий SMART</div>
            <div className="font-bold text-amber-800 text-2xl">{dashboard.weakest_criterion}</div>
          </div>
        </div>
      )}

      {/* Bar chart: avg smart by dept */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-800 mb-4">SMART-индекс по подразделениям</h2>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={barData} margin={{ top: 0, right: 10, left: -10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: '#64748b' }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis domain={[0, 5]} tick={{ fontSize: 11, fill: '#64748b' }} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="smart" name="SMART-индекс" radius={[4, 4, 0, 0]}>
              {barData.map((_, i) => (
                <rect key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Heatmap */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-800 mb-4">Матрица зрелости: Департаменты × SMART-критерии</h2>
        <DepartmentHeatmap departments={depts} />
      </div>

      {/* Trends */}
      {trendData.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">Тренды по кварталам</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData} margin={{ top: 0, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} />
              <YAxis yAxisId="smart" domain={[0, 5]} tick={{ fontSize: 11, fill: '#64748b' }} label={{ value: 'SMART', angle: -90, position: 'insideLeft', fontSize: 10, fill: '#94a3b8' }} />
              <YAxis yAxisId="pct" orientation="right" domain={[0, 100]} tick={{ fontSize: 11, fill: '#64748b' }} label={{ value: '%', position: 'insideRight', fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="smart" type="monotone" dataKey="smart" name="SMART-индекс" stroke="#1e3a5f" strokeWidth={2.5} dot={{ r: 3 }} />
              <Line yAxisId="pct" type="monotone" dataKey="strategic" name="Стратег. связка, %" stroke="#8b5cf6" strokeWidth={2} strokeDasharray="5 5" dot={false} />
              <Line yAxisId="pct" type="monotone" dataKey="impact" name="Impact-цели, %" stroke="#f59e0b" strokeWidth={2} strokeDasharray="3 3" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
