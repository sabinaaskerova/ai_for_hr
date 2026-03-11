import clsx from 'clsx'

const CRITERIA = ['avg_s', 'avg_m', 'avg_a', 'avg_r', 'avg_t']
const CRITERIA_LABELS = { avg_s: 'S', avg_m: 'M', avg_a: 'A', avg_r: 'R', avg_t: 'T' }

function cellColor(value) {
  if (value >= 4.0) return 'bg-emerald-500 text-white'
  if (value >= 3.5) return 'bg-emerald-300 text-emerald-900'
  if (value >= 3.0) return 'bg-amber-300 text-amber-900'
  if (value >= 2.5) return 'bg-orange-300 text-orange-900'
  return 'bg-red-400 text-white'
}

export default function DepartmentHeatmap({ departments }) {
  if (!departments?.length) {
    return <div className="text-center text-gray-400 py-8">Нет данных</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th className="text-left px-3 py-2 text-gray-600 font-semibold bg-gray-50 border border-gray-200 min-w-48">
              Подразделение
            </th>
            {CRITERIA.map((c) => (
              <th key={c} className="px-4 py-2 text-gray-600 font-semibold bg-gray-50 border border-gray-200 text-center w-16">
                {CRITERIA_LABELS[c]}
              </th>
            ))}
            <th className="px-4 py-2 text-gray-600 font-semibold bg-gray-50 border border-gray-200 text-center">
              SMART
            </th>
          </tr>
        </thead>
        <tbody>
          {departments.map((dept) => (
            <tr key={dept.department_id} className="hover:bg-gray-50/50">
              <td className="px-3 py-2 border border-gray-200 font-medium text-navy-700 text-xs">
                {dept.department_name}
              </td>
              {CRITERIA.map((c) => {
                const val = dept[c] ?? 0
                return (
                  <td key={c} className={clsx('px-2 py-2 border border-gray-200 text-center font-bold text-xs', cellColor(val))}>
                    {val.toFixed(1)}
                  </td>
                )
              })}
              <td className={clsx('px-2 py-2 border border-gray-200 text-center font-bold text-sm', cellColor(dept.avg_smart_index ?? 0))}>
                {(dept.avg_smart_index ?? 0).toFixed(1)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <span className="font-medium">Шкала:</span>
        {[
          { range: '≥4.0', cls: 'bg-emerald-500' },
          { range: '3.5-4.0', cls: 'bg-emerald-300' },
          { range: '3.0-3.5', cls: 'bg-amber-300' },
          { range: '2.5-3.0', cls: 'bg-orange-300' },
          { range: '<2.5', cls: 'bg-red-400' },
        ].map(({ range, cls }) => (
          <div key={range} className="flex items-center gap-1">
            <div className={clsx('w-3 h-3 rounded', cls)} />
            {range}
          </div>
        ))}
      </div>
    </div>
  )
}
