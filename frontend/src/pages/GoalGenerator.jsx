import { useState, useEffect, useCallback } from 'react'
import { Sparkles, Loader2, Search, User, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import clsx from 'clsx'
import GoalCard from '../components/GoalCard'
import { getEmployees, getDepartments, saveGoal } from '../api/client'
import { saveToHistory } from '../utils/history'

const QUARTERS = ['2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2']

export default function GoalGenerator() {
  const [search, setSearch] = useState('')
  const [employees, setEmployees] = useState([])
  const [depts, setDepts] = useState([])
  const [selectedEmp, setSelectedEmp] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [quarter, setQuarter] = useState('2025-Q4')
  const [nGoals, setNGoals] = useState(4)
  const [focus, setFocus] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamingGoals, setStreamingGoals] = useState([])
  const [streamProgress, setStreamProgress] = useState(null) // {current, total}
  const [warnings, setWarnings] = useState([])
  const [totalWeight, setTotalWeight] = useState(0)
  const [result, setResult] = useState(null) // финальный объект (совместимость)
  const [error, setError] = useState(null)
  const [acceptedIds, setAcceptedIds] = useState(new Set())
  const [rejectedIds, setRejectedIds] = useState(new Set())
  const [savedGoalIds, setSavedGoalIds] = useState({}) // index -> DB goal id
  const [saveErrorIds, setSaveErrorIds] = useState(new Set())

  useEffect(() => {
    getDepartments().then(setDepts).catch(() => {})
  }, [])

  const searchEmployees = useCallback(async (q) => {
    if (!q.trim()) { setEmployees([]); return }
    setSearchLoading(true)
    try {
      const res = await getEmployees(q)
      setEmployees(res.employees || [])
    } catch {
      setEmployees([])
    } finally {
      setSearchLoading(false)
    }
  }, [])

  useEffect(() => {
    const t = setTimeout(() => searchEmployees(search), 350)
    return () => clearTimeout(t)
  }, [search, searchEmployees])

  const handleGenerate = async () => {
    if (!selectedEmp) { setError('Выберите сотрудника'); return }
    setLoading(true)
    setError(null)
    setResult(null)
    setStreamingGoals([])
    setStreamProgress(null)
    setWarnings([])
    setTotalWeight(0)
    setAcceptedIds(new Set())
    setRejectedIds(new Set())
    setSavedGoalIds({})
    setSaveErrorIds(new Set())

    const collectedGoals = []
    let finalWarnings = []
    let finalWeight = 0

    try {
      const response = await fetch('/api/v1/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_id: selectedEmp.id,
          quarter,
          focus_priorities: focus || undefined,
          n_goals: nGoals,
        }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // последняя (возможно неполная) строка
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'start') {
              setStreamProgress({ current: 0, total: event.total })
            } else if (event.type === 'goal') {
              collectedGoals.push(event.goal)
              setStreamingGoals([...collectedGoals])
              setStreamProgress({ current: event.index + 1, total: event.index + 1 })
            } else if (event.type === 'done') {
              finalWarnings = event.warnings || []
              finalWeight = event.total_weight || 0
              setWarnings(finalWarnings)
              setTotalWeight(finalWeight)
              setResult({ goals: collectedGoals, warnings: finalWarnings, total_weight: finalWeight })
              saveToHistory({
                type: 'generation',
                employee: { id: selectedEmp.id, name: selectedEmp.full_name, position: selectedEmp.position, department: selectedEmp.department_name },
                quarter,
                goals: collectedGoals,
                warnings: finalWarnings,
                total_weight: finalWeight,
              })
            } else if (event.type === 'error') {
              setError(event.message)
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setStreamProgress(null)
    }
  }

  const goals = streamingGoals.length > 0 ? streamingGoals : (result?.goals ?? [])
  const typeDist = goals.reduce((acc, g) => {
    acc[g.goal_type] = (acc[g.goal_type] || 0) + 1
    return acc
  }, {})

  const deptName = depts.find((d) => d.id === selectedEmp?.department_id)?.name

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-navy-700 flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Генерация целей</h1>
          <p className="text-gray-500 text-sm">AI генерирует SMART-цели на основе ВНД и KPI подразделения</p>
        </div>
      </div>

      {/* Form */}
      <div className="card mb-6 space-y-4">
        {/* Employee search */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Сотрудник</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Поиск по имени..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setSelectedEmp(null) }}
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-navy-500"
            />
            {searchLoading && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-gray-400" />}
          </div>

          {/* Dropdown */}
          {employees.length > 0 && !selectedEmp && (
            <div className="border border-gray-200 rounded-lg mt-1 bg-white shadow-md max-h-48 overflow-y-auto">
              {employees.map((emp) => (
                <button
                  key={emp.id}
                  onClick={() => { setSelectedEmp(emp); setSearch(emp.full_name); setEmployees([]) }}
                  className="w-full text-left px-4 py-2.5 hover:bg-gray-50 flex items-center gap-3 border-b border-gray-50 last:border-0"
                >
                  <User className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <div>
                    <div className="text-sm font-medium text-gray-800">{emp.full_name}</div>
                    <div className="text-xs text-gray-500">{emp.position} · {emp.department_name}</div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Selected employee card */}
          {selectedEmp && (
            <div className="mt-2 bg-navy-50 rounded-lg px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-navy-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {selectedEmp.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
              </div>
              <div className="flex-1">
                <div className="font-semibold text-navy-800 text-sm">{selectedEmp.full_name}</div>
                <div className="text-xs text-navy-600">{selectedEmp.position} · {selectedEmp.department_name} · {selectedEmp.grade}</div>
                {selectedEmp.manager_name && (
                  <div className="text-xs text-navy-500 mt-0.5">Руководитель: {selectedEmp.manager_name}</div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Квартал</label>
            <select
              value={quarter}
              onChange={(e) => setQuarter(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
            >
              {QUARTERS.map((q) => <option key={q}>{q}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Количество целей</label>
            <select
              value={nGoals}
              onChange={(e) => setNGoals(Number(e.target.value))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
            >
              {[3, 4, 5].map((n) => <option key={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Фокус-приоритеты</label>
            <input
              type="text"
              placeholder="необязательно"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        <button onClick={handleGenerate} disabled={loading || !selectedEmp} className="btn-primary flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {loading ? 'Генерируем цели...' : 'Сгенерировать цели'}
        </button>
      </div>

      {/* Loading state (только пока нет ни одной цели ещё) */}
      {loading && goals.length === 0 && (
        <div className="card text-center py-12">
          <Loader2 className="w-10 h-10 animate-spin text-navy-500 mx-auto mb-4" />
          <div className="font-medium text-gray-700">AI генерирует цели...</div>
          <div className="text-sm text-gray-400 mt-1">RAG retrieval → LLM generation → Self-check</div>
        </div>
      )}

      {/* Results (показываем как только появляется первая цель) */}
      {goals.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="card mb-4 flex flex-wrap items-center gap-6">
            <div className="text-center">
              <div className={clsx('text-2xl font-bold', Math.abs(totalWeight - 100) < 2 ? 'text-emerald-600' : 'text-red-500')}>
                {totalWeight}%
              </div>
              <div className="text-xs text-gray-500">Сумма весов</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-navy-700">{goals.length}</div>
              <div className="text-xs text-gray-500">
                {loading ? (
                  <span className="flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    генерируем...
                  </span>
                ) : 'Целей'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">{acceptedIds.size}</div>
              <div className="text-xs text-gray-500">Принято</div>
            </div>
            <div className="flex gap-2 flex-wrap">
              {Object.entries(typeDist).map(([type, cnt]) => {
                const colors = {
                  'impact-based': 'bg-emerald-100 text-emerald-700',
                  'output-based': 'bg-blue-100 text-blue-700',
                  'activity-based': 'bg-orange-100 text-orange-700',
                }
                return (
                  <span key={type} className={clsx('badge', colors[type] ?? 'bg-gray-100 text-gray-600')}>
                    {type}: {cnt}
                  </span>
                )
              })}
            </div>
            {warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-amber-700 bg-amber-50 rounded-lg px-3 py-2 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                {w}
              </div>
            ))}
          </div>

          {/* Goal cards */}
          <div className="space-y-4">
            {goals.map((goal, i) => (
              <div key={i} className={clsx('transition-opacity', rejectedIds.has(i) && 'opacity-40')}>
                <GoalCard
                  goal={goal}
                  showActions
                  onAccept={async () => {
                    setAcceptedIds((s) => new Set([...s, i]))
                    try {
                      const saved = await saveGoal({
                        employee_id: selectedEmp.id,
                        quarter,
                        goal_text: goal.goal_text,
                        metric: goal.metric || null,
                        deadline: goal.deadline || null,
                        weight: goal.weight || null,
                        goal_type: goal.goal_type || null,
                        strategic_link: goal.strategic_link || null,
                        smart_s: goal.smart_scores?.specific ?? null,
                        smart_m: goal.smart_scores?.measurable ?? null,
                        smart_a: goal.smart_scores?.achievable ?? null,
                        smart_r: goal.smart_scores?.relevant ?? null,
                        smart_t: goal.smart_scores?.time_bound ?? null,
                        smart_index: goal.smart_index ?? null,
                        source_document: goal.source_document || null,
                        source_quote: goal.source_quote || null,
                        is_generated: true,
                      })
                      setSavedGoalIds((s) => ({ ...s, [i]: saved.id }))
                    } catch (e) {
                      console.error('Ошибка сохранения цели:', e)
                      setSaveErrorIds((s) => new Set([...s, i]))
                    }
                  }}
                  onReject={() => setRejectedIds((s) => new Set([...s, i]))}
                />
                {acceptedIds.has(i) && (
                  <div className="flex items-center gap-1.5 mt-1.5 text-xs font-medium px-1">
                    {saveErrorIds.has(i) ? (
                      <>
                        <XCircle className="w-3.5 h-3.5 text-red-500" />
                        <span className="text-red-500">Ошибка сохранения</span>
                      </>
                    ) : savedGoalIds[i] ? (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span className="text-emerald-600">Сохранена в БД (ID: {savedGoalIds[i]})</span>
                      </>
                    ) : (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-400" />
                        <span className="text-gray-400">Сохраняем...</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
            {/* Индикатор что ещё идёт генерация */}
            {loading && (
              <div className="card border-dashed border-2 border-navy-200 bg-navy-50 py-6 text-center">
                <Loader2 className="w-6 h-6 animate-spin text-navy-400 mx-auto mb-2" />
                <div className="text-sm text-navy-500">Обрабатываем следующую цель...</div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
