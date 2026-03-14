import { useState, useEffect } from 'react'
import { Target, Loader2, RefreshCw, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import SmartRadarChart from '../components/SmartRadarChart'
import BeforeAfter from '../components/BeforeAfter'
import { evaluateGoal, reformulateGoal, getDepartments } from '../api/client'
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

// Пороги для шкалы 0.0-1.0 (0.75 = 4/5, 0.5 = 3/5 нормализованное)
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
  const [departments, setDepartments] = useState([])
  const [form, setForm] = useState({ goal_text: '', position: '', department: '' })
  const [loading, setLoading] = useState(false)
  const [reformLoading, setReformLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [reformResult, setReformResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {})
  }, [])

  const handleEvaluate = async () => {
    if (!form.goal_text.trim() || !form.position.trim() || !form.department.trim()) {
      setError('Заполните все поля')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    setReformResult(null)
    try {
      const res = await evaluateGoal(form)
      setResult(res)
      saveToHistory({ type: 'evaluation', input: form, result: res })
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
      const res = await reformulateGoal({ goal_text: form.goal_text, position: form.position, department: form.department })
      setReformResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setReformLoading(false)
    }
  }

  // API теперь возвращает smart_detail (SmartEvaluationResult с S/M/A/R/T)
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
          <p className="text-gray-500 text-sm">AI-оценка по методологии SMART + стратегическая связка</p>
        </div>
      </div>

      {/* Form */}
      <div className="card mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Должность</label>
            <input
              type="text"
              placeholder="напр. HR бизнес-партнёр"
              value={form.position}
              onChange={(e) => setForm({ ...form, position: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Подразделение</label>
            <select
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500 bg-white"
            >
              <option value="">— Выбрать —</option>
              {departments.map((d) => (
                <option key={d.id} value={d.name}>{d.name}</option>
              ))}
              {departments.length === 0 && (
                <>
                  <option>HR и управление персоналом</option>
                  <option>Добыча</option>
                  <option>Финансы и экономика</option>
                  <option>Цифровая трансформация</option>
                </>
              )}
            </select>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Цель для оценки</label>
          <textarea
            rows={4}
            placeholder="Введите формулировку цели..."
            value={form.goal_text}
            onChange={(e) => setForm({ ...form, goal_text: e.target.value })}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500 resize-none"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm mb-4">
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
            {/* Big SMART index (из ТЗ: smart_index на уровне ответа) */}
            <div className="card text-center">
              <div className={clsx('text-5xl font-bold mb-1', scoreColor(result.smart_index))}>
                {result.smart_index?.toFixed(2)}
              </div>
              <div className="text-gray-500 text-sm">SMART-индекс (0–1)</div>
              <div className="mt-3">
                {/* Передаём smart_scores (плоский формат) для radar */}
                <SmartRadarChart smart={result.smart_scores} size={220} />
              </div>
            </div>

            {/* Badges */}
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

            {/* F-20: предупреждение о достижимости */}
            {result.achievability_warning && (
              <div className="card border border-orange-200 bg-orange-50">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-semibold text-orange-700 mb-1">Достижимость (исторические данные)</div>
                    <p className="text-xs text-orange-600">{result.achievability_warning}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Рекомендации (из ТЗ: recommendations[]) */}
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
            <h2 className="font-semibold text-gray-800">Детализация по критериям</h2>
            {['S', 'M', 'A', 'R', 'T'].map((k) => (
              <CriterionCard key={k} letter={k} data={smartDetail[k]} />
            ))}

            {smartDetail?.reformulation_hint && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div className="text-xs font-semibold text-amber-700 uppercase mb-1">Подсказка для переформулировки</div>
                <p className="text-sm text-amber-800">{smartDetail.reformulation_hint}</p>
              </div>
            )}

            {/* improved_goal из ТЗ */}
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
