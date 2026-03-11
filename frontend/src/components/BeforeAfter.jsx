import { ArrowRight } from 'lucide-react'
import SmartRadarChart from './SmartRadarChart'
import clsx from 'clsx'

function ScoreRow({ label, before, after }) {
  const diff = after - before
  return (
    <div className="flex items-center justify-between text-sm py-1 border-b border-gray-50 last:border-0">
      <span className="font-medium text-gray-600 w-8">{label}</span>
      <span className="text-gray-400">{before.toFixed(2)}</span>
      <ArrowRight className="w-3 h-3 text-gray-300" />
      <span className={clsx('font-semibold', diff > 0 ? 'text-emerald-600' : diff < 0 ? 'text-red-500' : 'text-gray-500')}>
        {after.toFixed(2)}
      </span>
      <span className={clsx('text-xs ml-2 font-medium', diff > 0 ? 'text-emerald-500' : diff < 0 ? 'text-red-400' : 'text-gray-400')}>
        {diff > 0 ? `+${diff.toFixed(2)}` : diff.toFixed(2)}
      </span>
    </div>
  )
}

export default function BeforeAfter({
  original,
  reformulated,
  originalSmart,
  reformulatedSmart,
  originalSmartIndex,
  reformulatedSmartIndex,
  improvements = [],
}) {
  // Определяем индексы: либо из пропсов напрямую, либо из объекта smart_detail
  const origIdx = originalSmartIndex ?? originalSmart?.smart_index
  const refIdx = reformulatedSmartIndex ?? reformulatedSmart?.smart_index
  const idxColor = refIdx >= 0.75 ? 'text-emerald-600' : refIdx >= 0.5 ? 'text-amber-500' : 'text-red-500'

  return (
    <div className="space-y-6">
      {/* Radar comparison — передаём SmartEvaluationResult (detail) с S/M/A/R/T */}
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4 text-center">
          Сравнение SMART-оценок: До / После
        </h3>
        <SmartRadarChart smart={originalSmart} comparedSmart={reformulatedSmart} size={280} />
      </div>

      {/* Score deltas */}
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-3">Изменения по критериям</h3>
        {['S', 'M', 'A', 'R', 'T'].map((k) => (
          <ScoreRow
            key={k}
            label={k}
            before={originalSmart?.[k]?.score ?? 0}
            after={reformulatedSmart?.[k]?.score ?? 0}
          />
        ))}
        <div className="mt-3 pt-3 border-t border-gray-200 flex items-center justify-between">
          <span className="font-semibold text-gray-700">SMART-индекс</span>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">{origIdx?.toFixed(2)}</span>
            <ArrowRight className="w-3 h-3 text-gray-300" />
            <span className={clsx('font-bold text-lg', idxColor)}>{refIdx?.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Goal texts */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card border-l-4 border-l-red-300">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Исходная цель</div>
          <p className="text-sm text-gray-700 leading-relaxed">{original}</p>
        </div>
        <div className="card border-l-4 border-l-emerald-400">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Переформулированная цель</div>
          <p className="text-sm text-gray-900 font-medium leading-relaxed">{reformulated}</p>
        </div>
      </div>

      {/* Improvements */}
      {improvements.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-3">Что улучшено</h3>
          <ul className="space-y-2">
            {improvements.map((imp, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="text-emerald-500 font-bold mt-0.5">✓</span>
                {imp}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
