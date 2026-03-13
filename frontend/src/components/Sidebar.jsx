import { NavLink } from 'react-router-dom'
import { BarChart3, Target, Sparkles, FileSearch, Activity, History } from 'lucide-react'
import clsx from 'clsx'

const links = [
  { to: '/', label: 'Оценка целей', icon: Target, exact: true },
  { to: '/generate', label: 'Генерация целей', icon: Sparkles },
  { to: '/analytics', label: 'Аналитика', icon: BarChart3 },
  { to: '/documents', label: 'Документы (ВНД)', icon: FileSearch },
  { to: '/history', label: 'История', icon: History },
]

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-navy-700 flex flex-col z-40">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-navy-600">
        <div className="flex items-center gap-2">
          <Activity className="text-amber-400 w-6 h-6 flex-shrink-0" />
          <div>
            <div className="text-white font-bold text-sm leading-tight">HR Goals AI</div>
            <div className="text-navy-300 text-xs">КМГ-Кумколь</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {links.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-amber-500 text-white'
                  : 'text-navy-200 hover:bg-navy-600 hover:text-white'
              )
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-navy-600">
        <div className="text-navy-400 text-xs">
          <div className="font-medium text-navy-300">Хакатон КМГ-Кумколь</div>
          <div>Demo Day — 30.03.2026</div>
        </div>
      </div>
    </aside>
  )
}
