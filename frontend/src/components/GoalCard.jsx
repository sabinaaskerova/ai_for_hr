import { useState } from 'react'
import { ChevronDown, ChevronUp, CheckCircle, XCircle, AlertCircle, BookOpen, GitBranch } from 'lucide-react'
import clsx from 'clsx'
import SmartRadarChart from './SmartRadarChart'

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

// Пороги для шкалы 0.0-1.0
function SmartIndex({ score }) {
  const color = score >= 0.75 ? 'text-emerald-600' : score >= 0.5 ? 'text-amber-500' : 'text-red-500'
  return (
    <div className="text-center">
      <div className={clsx('text-3xl font-bold', color)}>{score?.toFixed(2)}</div>
      <div className="text-xs text-gray-500 mt-0.5">SMART-индекс</div>
    </div>
  )
}

export default function GoalCard({ goal, onAccept, onReject, onEdit, showActions = false }) {
  const [sourceOpen, setSourceOpen] = useState(false)
  const [radarOpen, setRadarOpen] = useState(false)

  const typeConf = GOAL_TYPE_CONFIG[goal.goal_type] ?? GOAL_TYPE_CONFIG['output-based']
  const linkConf = LINK_CONFIG[goal.strategic_link] ?? LINK_CONFIG['операционная']
  // API генератора возвращает smart_scores (плоский) и smart_index (float 0-1)
  const smartScores = goal.smart_scores
  const smartIndex = goal.smart_index

  return (
    <div className={clsx(
      'card border-l-4 transition-shadow hover:shadow-md',
      goal.requires_review ? 'border-l-amber-400' : 'border-l-navy-600'
    )}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1">
          <p className="text-gray-900 font-medium leading-snug">{goal.goal_text}</p>
          {goal.requires_review && (
            <div className="flex items-center gap-1.5 mt-2 text-amber-600 text-xs font-medium">
              <AlertCircle className="w-3.5 h-3.5" />
              Требует проверки (SMART &lt; 0.63)
            </div>
          )}
        </div>
        {smartIndex != null && <SmartIndex score={smartIndex} />}
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className={clsx('badge', typeConf.color)}>{typeConf.label}</span>
        <span className={clsx('badge', linkConf.color)}>{linkConf.label}</span>
        {goal.weight && (
          <span className="badge bg-navy-100 text-navy-700">Вес: {goal.weight}%</span>
        )}
        {goal.deadline && (
          <span className="badge bg-gray-100 text-gray-600">До {goal.deadline}</span>
        )}
      </div>

      {/* F-14: Каскадирование от руководителя */}
      {goal.cascade_from && (
        <div className="flex items-start gap-2 bg-purple-50 border border-purple-100 rounded-lg px-3 py-2 mb-3">
          <GitBranch className="w-3.5 h-3.5 text-purple-500 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <span className="text-xs font-semibold text-purple-700">
              Каскадировано от: {goal.cascade_from.manager_name}
            </span>
            <p className="text-xs text-purple-600 mt-0.5 line-clamp-2 italic">
              «{goal.cascade_from.manager_goal}»
            </p>
          </div>
        </div>
      )}

      {/* Metric */}
      {goal.metric && (
        <div className="text-sm text-gray-600 mb-3">
          <span className="font-medium text-gray-700">Метрика: </span>{goal.metric}
        </div>
      )}

      {/* Reasoning */}
      {goal.reasoning && (
        <p className="text-sm text-gray-500 mb-3 italic">{goal.reasoning}</p>
      )}

      {/* Source document (collapsible) */}
      {goal.source_document && (
        <div className="border border-gray-100 rounded-lg overflow-hidden mb-3">
          <button
            onClick={() => setSourceOpen((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-navy-500" />
              <span>{goal.source_document}</span>
            </div>
            {sourceOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {sourceOpen && goal.source_quote && (
            <div className="px-3 pb-3 text-xs text-gray-500 border-t border-gray-100 pt-2 italic">
              «{goal.source_quote}»
            </div>
          )}
        </div>
      )}

      {/* Mini radar (collapsible) — использует плоский формат SmartScores */}
      {smartScores && (
        <div className="border border-gray-100 rounded-lg overflow-hidden mb-3">
          <button
            onClick={() => setRadarOpen((v) => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
          >
            <span>SMART-оценка</span>
            {radarOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          {radarOpen && (
            <div className="px-2 pb-2 border-t border-gray-100">
              <SmartRadarChart smart={smartScores} size={200} />
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      {showActions && (
        <div className="flex gap-2 pt-1">
          {onAccept && (
            <button
              onClick={() => onAccept(goal)}
              className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
            >
              <CheckCircle className="w-4 h-4" /> Принять
            </button>
          )}
          {onReject && (
            <button
              onClick={() => onReject(goal)}
              className="flex items-center gap-1.5 text-xs font-medium text-red-500 hover:text-red-600 transition-colors"
            >
              <XCircle className="w-4 h-4" /> Отклонить
            </button>
          )}
        </div>
      )}
    </div>
  )
}
