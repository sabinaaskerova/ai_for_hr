import { useState, useEffect, useCallback } from 'react'
import { Target, Loader2, RefreshCw, ChevronDown, ChevronUp, AlertTriangle, Search, User, Copy } from 'lucide-react'
import clsx from 'clsx'
import SmartRadarChart from '../components/SmartRadarChart'
import BeforeAfter from '../components/BeforeAfter'
import { evaluateGoal, reformulateGoal, getEmployees } from '../api/client'
import { saveToHistory } from '../utils/history'

const GOAL_TYPE_CONFIG = {
  'impact-based': { label: 'Impact-based', color: 'bg-emerald-100 text-emerald-700' },
  'output-based': { label: 'Output-based', color: 'bg-blue-100 text-blue-700' },
  'activity-based': { label: 'Activity-based', color: 'bg-orange-100 text-orange-700' },
}
const LINK_CONFIG = {
  'стратегическая': { label: 'Стратегическая', color: 'bg-purple-100 text-purple-700' },
  'функциональная': { label: 'Функциональная', color: 'bg-blue-100 text-blue-700' },
  'операционная': { label: 'Операционная', color: 'bg-gray-100 text-gray-600' },
  'нет связки': { label: 'Нет связки', color: 'bg-red-100 text-red-600' },
}

const CRITERION_NAMES = { S: 'Specific', M: 'Measurable', A: 'Achievable', R: 'Relevant', T: 'Time-bound' }

const QUARTERS = ['2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2']

function scoreColor(s) {
  if (s >= 0.75) return 'text-emerald-600'
  if (s >= 0.5) return 'text-amber-500'
  return 'text-red-500'
}
function scoreBg(s) {
  if (s >= 0.75) return 'bg-emerald-50 border-emerald-200'
  if (s >= 0.5) return 'bg-amber-50 border-amber-200'
  return 'bg-red-50 border-red-200'
}

function CriterionCard({ letter, data }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={clsx('rounded-xl border p-4 transition-shadow hover:shadow-sm', scoreBg(data.score))}>
      <div className="flex items-start justify-between cursor-pointer" onClick={() => setOpen((v) => !v)}>
        <div className="flex items-center gap-3">
          <div className={clsx('w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0',
            data.score >= 0.75 ? 'bg-emerald-500' : data.score >= 0.5 ? 'bg-amber-400' : 'bg-red-400'
          )}>
            {letter}
          </div>
          <div>
            <div className="font-semibold text-gray-800 text-sm">{CRITERION_NAMES[letter]}</div>
            <div className={clsx('font-bold text-lg leading-none', scoreColor(data.score))}>
              {(data.score * 100).toFixed(0)}%
            </div>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400 mt-1" /> : <ChevronDown className="w-4 h-4 text-gray-400 mt-1" />}
      </div>
      {open && (
        <div className="mt-3 space-y-2 pt-3 border-t border-gray-200">
          <p className="text-sm text-gray-700 leading-relaxed">{data.reasoning}</p>
          {data.recommendation && (
            <div className="bg-white rounded-lg p-3 border border-gray-100">
              <div className="text-xs font-semibold text-navy-600 uppercase tracking-wide mb-1">Рекомендация</div>
              <p className="text-sm text-gray-700">{data.recommendation}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function GoalEvaluator() {
  const [search, setSearch] = useState('')
  const [employees, setEmployees] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [selectedEmp, setSelectedEmp] = useState(null)
  const [quarter, setQuarter] = useState('2026-Q1')
  const [goalText, setGoalText] = useState('')
  const [loading, setLoading] = useState(false)
  const [reformLoading, setReformLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [reformResult, setReformResult] = useState(null)
  const [error, setError] = useState(null)

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

  const handleEvaluate = async () => {
    if (!selectedEmp) { setError('Выберите сотрудника'); return }
    if (!goalText.trim()) { setError('Введите текст цели'); return }
    setLoading(true)
    setError(null)
    setResult(null)
    setReformResult(null)
    try {
      const res = await evaluateGoal({
        goal_text: goalText,
        position: selectedEmp.position,
        department: selectedEmp.department_name,
        employee_id: selectedEmp.id,
        quarter,
      })
      setResult(res)
      saveToHistory({
        type: 'evaluation',
        input: { goal_text: goalText, position: selectedEmp.position, department: selectedEmp.department_name, employee_id: selectedEmp.id },
        result: res,
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleReformulate = async () => {
    setReformLoading(true)
    setError(null)
    try {
      const res = await reformulateGoal({
        goal_text: goalText,
        position: selectedEmp?.position || '',
        department: selectedEmp?.department_name || '',
      })
      setReformResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setReformLoading(false)
    }
  }

  const smartDetail = result?.smart_detail
  const link = result?.strategic_link
  const typeConf = GOAL_TYPE_CONFIG[smartDetail?.goal_type] ?? GOAL_TYPE_CONFIG['output-based']
  const linkConf = LINK_CONFIG[link?.link_level] ?? LINK_CONFIG['операционная']

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-navy-700 flex items-center justify-center">
          <Target className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Оценка цели</h1>
          <p className="text-gray-500 text-sm">AI-оценка по методологии SMART + стратегическая связка + проверка дублирования</p>
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

        {/* Quarter */}
        <div className="w-48">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Квартал</label>
          <select
            value={quarter}
            onChange={(e) => setQuarter(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
          >
            {QUARTERS.map((q) => <option key={q}>{q}</option>)}
          </select>
        </div>

        {/* Goal text */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Цель для оценки</label>
          <textarea
            rows={4}
            placeholder="Введите формулировку цели..."
            value={goalText}
            onChange={(e) => setGoalText(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500 resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button onClick={handleEvaluate} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Target className="w-4 h-4" />}
            {loading ? 'Оцениваем...' : 'Оценить'}
          </button>
          {result?.smart_detail?.reformulation_suggested && (
            <button onClick={handleReformulate} disabled={reformLoading} className="btn-secondary flex items-center gap-2">
              {reformLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              {reformLoading ? 'Переформулируем...' : 'Переформулировать'}
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {result && !reformResult && (
        <div className="grid grid-cols-5 gap-6">
          {/* Left: radar + meta */}
          <div className="col-span-2 space-y-4">
            <div className="card text-center">
              <div className={clsx('text-5xl font-bold mb-1', scoreColor(result.smart_index))}>
                {result.smart_index?.toFixed(2)}
              </div>
              <div className="text-gray-500 text-sm">SMART-индекс (0–1)</div>
              <div className="mt-3">
                <SmartRadarChart smart={result.smart_scores} size={220} />
              </div>
            </div>

            <div className="card space-y-3">
              <div>
                <div className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Тип цели</div>
                <span className={clsx('badge', typeConf.color)}>{typeConf.label}</span>
                <p className="text-xs text-gray-500 mt-1.5">{smartDetail?.goal_type_reasoning}</p>
              </div>
              <div>
                <div className="text-xs font-semibold text-gray-500 uppercase mb-1.5">Стратегическая связка</div>
                <span className={clsx('badge', linkConf.color)}>{linkConf.label}</span>
                {link?.source_name && (
                  <p className="text-xs text-gray-500 mt-1.5">
                    <span className="font-medium">Источник:</span> {link.source_name}
                  </p>
                )}
                {link?.source_quote && (
                  <p className="text-xs text-gray-400 mt-1 italic">«{link.source_quote.slice(0, 120)}...»</p>
                )}
                <p className="text-xs text-gray-500 mt-1.5">{link?.reasoning}</p>
              </div>
            </div>

            {/* F-21: предупреждение о дублировании */}
            {result.duplicate_warning && (
              <div className="card border border-amber-200 bg-amber-50">
                <div className="flex items-start gap-2">
                  <Copy className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-semibold text-amber-700 mb-1">Дублирование целей (F-21)</div>
                    <p className="text-xs text-amber-600">{result.duplicate_warning}</p>
                  </div>
                </div>
              </div>
            )}

            {/* F-20: предупреждение о достижимости */}
            {result.achievability_warning && (
              <div className="card border border-orange-200 bg-orange-50">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-semibold text-orange-700 mb-1">Достижимость (F-20)</div>
                    <p className="text-xs text-orange-600">{result.achievability_warning}</p>
                  </div>
                </div>
              </div>
            )}

            {result.recommendations?.length > 0 && (
              <div className="card">
                <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Рекомендации</div>
                <ul className="space-y-1.5">
                  {result.recommendations.map((rec, i) => (
                    <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                      <span className="text-amber-500 font-bold mt-0.5">→</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Right: criteria cards */}
          <div className="col-span-3 space-y-3">
            <h2 className="font-semibold text-gray-800">Детализация по критериям SMART</h2>
            {['S', 'M', 'A', 'R', 'T'].map((k) => (
              <CriterionCard key={k} letter={k} data={smartDetail[k]} />
            ))}

            {smartDetail?.reformulation_hint && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div className="text-xs font-semibold text-amber-700 uppercase mb-1">Подсказка для переформулировки</div>
                <p className="text-sm text-amber-800">{smartDetail.reformulation_hint}</p>
              </div>
            )}

            {result.improved_goal && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                <div className="text-xs font-semibold text-emerald-700 uppercase mb-1">Улучшенная формулировка</div>
                <p className="text-sm text-emerald-800">{result.improved_goal}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Before/After */}
      {reformResult && (
        <BeforeAfter
          original={reformResult.original_goal}
          reformulated={reformResult.reformulated_goal}
          originalSmart={reformResult.original_smart_detail}
          reformulatedSmart={reformResult.reformulated_smart_detail}
          originalSmartIndex={reformResult.original_smart_index}
          reformulatedSmartIndex={reformResult.reformulated_smart_index}
          improvements={reformResult.improvements}
        />
      )}
    </div>
  )
}
