import { useState, useEffect } from 'react'
import { FileSearch, Search, Loader2, BookOpen, X } from 'lucide-react'
import clsx from 'clsx'
import { searchDocuments, getDepartments } from '../api/client'

const DOC_TYPES = [
  { value: '', label: 'Все типы' },
  { value: 'strategy', label: 'Стратегия' },
  { value: 'kpi_framework', label: 'KPI-фреймворк' },
  { value: 'policy', label: 'Политика' },
  { value: 'regulation', label: 'Регламент' },
]

const TYPE_CONFIG = {
  strategy: { label: 'Стратегия', color: 'bg-purple-100 text-purple-700' },
  kpi_framework: { label: 'KPI-фреймворк', color: 'bg-blue-100 text-blue-700' },
  policy: { label: 'Политика', color: 'bg-emerald-100 text-emerald-700' },
  regulation: { label: 'Регламент', color: 'bg-orange-100 text-orange-700' },
}

function highlightText(text, query) {
  if (!query.trim()) return text
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  const parts = text.split(regex)
  return parts.map((part, i) =>
    regex.test(part) ? <mark key={i} className="bg-amber-200 text-amber-900 rounded px-0.5">{part}</mark> : part
  )
}

export default function DocumentBrowser() {
  const [query, setQuery] = useState('')
  const [deptId, setDeptId] = useState('')
  const [docType, setDocType] = useState('')
  const [departments, setDepartments] = useState([])
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDepartments().then(setDepartments).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await searchDocuments({
        query,
        department_id: deptId ? Number(deptId) : undefined,
        doc_type: docType || undefined,
        top_k: 10,
      })
      setResults(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch()
  }

  const clearSearch = () => {
    setQuery('')
    setResults(null)
    setError(null)
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-navy-700 flex items-center justify-center">
          <FileSearch className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Документы ВНД</h1>
          <p className="text-gray-500 text-sm">Семантический поиск по внутренним нормативным документам</p>
        </div>
      </div>

      {/* Search form */}
      <div className="card mb-6">
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Поиск по содержимому ВНД... (напр. «KPI инженера добычи», «SMART-цели»)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-9 pr-10 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-navy-500"
          />
          {query && (
            <button onClick={clearSearch} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <div className="flex gap-3 mb-4">
          <select
            value={deptId}
            onChange={(e) => setDeptId(e.target.value)}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
          >
            <option value="">Все подразделения</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy-500"
          >
            {DOC_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <button onClick={handleSearch} disabled={loading || !query.trim()} className="btn-primary flex items-center gap-2 whitespace-nowrap">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Найти
          </button>
        </div>

        {/* Quick queries */}
        <div className="flex flex-wrap gap-2">
          {[
            'SMART-цели требования',
            'KPI инженера добычи',
            'снижение текучести кадров',
            'стратегия развития персонала',
            'охрана труда LTIFR',
            'цифровая трансформация',
          ].map((q) => (
            <button
              key={q}
              onClick={() => { setQuery(q); }}
              className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 px-3 py-1.5 rounded-full transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 text-red-700 text-sm mb-4">{error}</div>
      )}

      {/* Results */}
      {results && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm text-gray-500">
              Найдено результатов: <span className="font-semibold text-gray-700">{results.total_found}</span>
            </div>
          </div>

          {results.results.length === 0 ? (
            <div className="card text-center py-12 text-gray-400">
              <FileSearch className="w-10 h-10 mx-auto mb-3 opacity-40" />
              По запросу «{query}» ничего не найдено
            </div>
          ) : (
            <div className="space-y-4">
              {results.results.map((doc, i) => {
                const typeConf = TYPE_CONFIG[doc.doc_type] ?? { label: doc.doc_type, color: 'bg-gray-100 text-gray-600' }
                const relevancePct = Math.round(doc.relevance_score * 100)
                return (
                  <div key={i} className="card hover:shadow-md transition-shadow">
                    {/* Doc header */}
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex items-start gap-3 flex-1">
                        <BookOpen className="w-4 h-4 text-navy-500 flex-shrink-0 mt-0.5" />
                        <div>
                          <h3 className="font-semibold text-navy-800 text-sm leading-snug">{doc.title}</h3>
                          {doc.department_name && (
                            <span className="text-xs text-gray-400">{doc.department_name}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={clsx('badge', typeConf.color)}>{typeConf.label}</span>
                        <div className="flex items-center gap-1">
                          <div className="h-1.5 w-16 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={clsx('h-full rounded-full', relevancePct >= 70 ? 'bg-emerald-400' : relevancePct >= 50 ? 'bg-amber-400' : 'bg-gray-300')}
                              style={{ width: `${relevancePct}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-400">{relevancePct}%</span>
                        </div>
                      </div>
                    </div>

                    {/* Relevant chunk */}
                    <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-700 leading-relaxed border border-gray-100">
                      {highlightText(doc.chunk_text, query)}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!results && !loading && (
        <div className="text-center py-16 text-gray-300">
          <FileSearch className="w-16 h-16 mx-auto mb-4 opacity-30" />
          <div className="text-gray-400 font-medium">Введите запрос для поиска по ВНД</div>
          <div className="text-sm text-gray-300 mt-1">Используется семантический поиск с BGE-M3</div>
        </div>
      )}
    </div>
  )
}
