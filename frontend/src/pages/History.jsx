import { useState, useEffect } from 'react'
import { History as HistoryIcon, Trash2, Target, Sparkles, Clock, ChevronDown, ChevronUp, X } from 'lucide-react'
import clsx from 'clsx'
import { getHistory, clearHistory, deleteHistoryItem } from '../utils/history'

const SMART_LABELS = { S: 'Specific', M: 'Measurable', A: 'Achievable', R: 'Relevant', T: 'Time-bound' }
const TYPE_COLORS = {
  'impact-based': 'bg-emerald-100 text-emerald-700',
  'output-based': 'bg-blue-100 text-blue-700',
  'activity-based': 'bg-orange-100 text-orange-700',
}
const LINK_COLORS = {
  'стратегическая': 'bg-purple-100 text-purple-700',
  'функциональная': 'bg-blue-100 text-blue-700',
  'операционная': 'bg-gray-100 text-gray-600',
}

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function SmartBadge({ scores, index }) {
  if (!scores || !index) return null
  const pct = Math.round(index * 100)
  const color = pct >= 75 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-1.5">
      <div className={clsx('w-2 h-2 rounded-full', color)} />
      <span className="text-xs text-gray-500">SMART {pct}%</span>
    </div>
  )
}

function EvaluationItem({ item }) {
  const [open, setOpen] = useState(false)
  const { input, result } = item
  const pct = result?.smart_index != null ? Math.round(result.smart_index * 100) : null
  const color = pct >= 75 ? 'text-emerald-600' : pct >= 50 ? 'text-amber-500' : 'text-red-500'

  // goal_type может быть в result.smart_detail.goal_type или result.goal_type
  const goalType = result?.smart_detail?.goal_type ?? result?.goal_type

  // SMART bars: используем smart_detail (S/M/A/R/T с .score) если есть,
  // иначе smart_scores (specific/measurable/... — flat floats)
  const smartBars = result?.smart_detail
    ? ['S', 'M', 'A', 'R', 'T'].map((letter) => ({
        letter,
        score: result.smart_detail[letter]?.score ?? 0,
      }))
    : result?.smart_scores
    ? [
        { letter: 'S', score: result.smart_scores.specific ?? 0 },
        { letter: 'M', score: result.smart_scores.measurable ?? 0 },
        { letter: 'A', score: result.smart_scores.achievable ?? 0 },
        { letter: 'R', score: result.smart_scores.relevant ?? 0 },
        { letter: 'T', score: result.smart_scores.time_bound ?? 0 },
      ]
    : null

  // strategic_link может быть объектом StrategicLinkResult или строкой
  const strategicLevel = typeof result?.strategic_link === 'string'
    ? result.strategic_link
    : result?.strategic_link?.link_level
  const strategicSource = typeof result?.strategic_link === 'string'
    ? result?.strategic_source
    : result?.strategic_link?.source_name

  const recommendations = Array.isArray(result?.recommendations) ? result.recommendations : []

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3 cursor-pointer" onClick={() => setOpen(v => !v)}>
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
            <Target className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-gray-800 line-clamp-2">{input?.goal_text}</div>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              <span className="text-xs text-gray-400">{input?.position} · {input?.department}</span>
              {pct !== null && <span className={clsx('text-xs font-bold', color)}>SMART {pct}%</span>}
              {goalType && (
                <span className={clsx('badge text-xs', TYPE_COLORS[goalType] ?? 'bg-gray-100 text-gray-600')}>
                  {goalType}
                </span>
              )}
            </div>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" /> : <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" />}
      </div>

      {open && result && (
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
          {smartBars && (
            <div className="grid grid-cols-5 gap-2">
              {smartBars.map(({ letter, score: s }) => {
                const barColor = s >= 0.75 ? 'bg-emerald-400' : s >= 0.5 ? 'bg-amber-400' : 'bg-red-400'
                return (
                  <div key={letter} className="text-center">
                    <div className="text-xs font-bold text-gray-600 mb-1">{letter}</div>
                    <div className="h-1.5 bg-gray-100 rounded-full mb-1">
                      <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${Math.round(s * 100)}%` }} />
                    </div>
                    <div className="text-xs text-gray-500">{Math.round(s * 100)}%</div>
                  </div>
                )
              })}
            </div>
          )}
          {strategicLevel && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-gray-500">Связка:</span>
              <span className={clsx('badge text-xs', LINK_COLORS[strategicLevel] ?? 'bg-gray-100 text-gray-600')}>
                {strategicLevel}
              </span>
              {strategicSource && (
                <span className="text-xs text-gray-400 truncate">· {strategicSource}</span>
              )}
            </div>
          )}
          {recommendations.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">Рекомендации</div>
              <ul className="space-y-1">
                {recommendations.map((r, i) => (
                  <li key={i} className="text-xs text-gray-600 bg-amber-50 rounded px-2 py-1">· {r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function GenerationItem({ item }) {
  const [open, setOpen] = useState(false)
  const { employee, quarter, goals, warnings, total_weight } = item

  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3 cursor-pointer" onClick={() => setOpen(v => !v)}>
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-amber-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-gray-800">{employee?.name}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-400">{employee?.position} · {employee?.department}</span>
              <span className="text-xs text-gray-400">·</span>
              <span className="text-xs font-medium text-navy-600">{quarter}</span>
              <span className="badge bg-gray-100 text-gray-600 text-xs">{goals?.length} целей</span>
              <span className={clsx('text-xs font-bold', Math.abs((total_weight||0) - 100) < 2 ? 'text-emerald-600' : 'text-amber-500')}>
                {total_weight}%
              </span>
            </div>
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" /> : <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0 mt-1" />}
      </div>

      {open && goals && (
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
          {goals.map((g, i) => (
            <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
              <div className="text-sm text-gray-800 mb-2">{g.goal_text}</div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={clsx('badge text-xs', TYPE_COLORS[g.goal_type] ?? 'bg-gray-100 text-gray-600')}>{g.goal_type}</span>
                {g.strategic_link && (
                  <span className={clsx('badge text-xs', LINK_COLORS[g.strategic_link] ?? 'bg-gray-100 text-gray-600')}>{g.strategic_link}</span>
                )}
                <SmartBadge scores={g.smart_scores} index={g.smart_index} />
                <span className="text-xs text-gray-400">Вес: {g.weight}%</span>
                {g.deadline && <span className="text-xs text-gray-400">Срок: {g.deadline}</span>}
              </div>
              {g.source_document && (
                <div className="text-xs text-gray-400 mt-1.5 italic">Источник: {g.source_document}</div>
              )}
            </div>
          ))}
          {warnings?.length > 0 && warnings.map((w, i) => (
            <div key={i} className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-1.5">{w}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function HistoryPage() {
  const [history, setHistory] = useState([])
  const [filter, setFilter] = useState('all') // all | evaluation | generation

  useEffect(() => {
    setHistory(getHistory())
  }, [])

  const handleDelete = (id) => {
    deleteHistoryItem(id)
    setHistory(getHistory())
  }

  const handleClear = () => {
    if (confirm('Очистить всю историю?')) {
      clearHistory()
      setHistory([])
    }
  }

  const filtered = filter === 'all' ? history : history.filter(h => h.type === filter)
  const evalCount = history.filter(h => h.type === 'evaluation').length
  const genCount = history.filter(h => h.type === 'generation').length

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-navy-700 flex items-center justify-center">
            <HistoryIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">История запросов</h1>
            <p className="text-gray-500 text-sm">Оценки и генерации сохраняются в браузере</p>
          </div>
        </div>
        {history.length > 0 && (
          <button onClick={handleClear} className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 font-medium">
            <Trash2 className="w-4 h-4" />
            Очистить всё
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-6">
        {[
          { key: 'all', label: `Все (${history.length})` },
          { key: 'evaluation', label: `Оценки (${evalCount})` },
          { key: 'generation', label: `Генерации (${genCount})` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              filter === key
                ? 'bg-navy-700 text-white'
                : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16">
          <HistoryIcon className="w-12 h-12 mx-auto mb-4 text-gray-200" />
          <div className="text-gray-400 font-medium">История пуста</div>
          <div className="text-sm text-gray-300 mt-1">Оцените или сгенерируйте цели — они появятся здесь</div>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item) => (
            <div key={item.id} className="relative group">
              {item.type === 'evaluation' ? (
                <EvaluationItem item={item} />
              ) : (
                <GenerationItem item={item} />
              )}
              <div className="absolute top-3 right-3 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="flex items-center gap-1 text-xs text-gray-400">
                  <Clock className="w-3 h-3" />
                  {formatDate(item.timestamp)}
                </span>
                <button
                  onClick={() => handleDelete(item.id)}
                  className="text-gray-300 hover:text-red-400 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
