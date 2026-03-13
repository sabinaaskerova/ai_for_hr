const HISTORY_KEY = 'hr_goals_history'
const MAX_ITEMS = 50

export function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
  } catch {
    return []
  }
}

export function saveToHistory(item) {
  try {
    const history = getHistory()
    history.unshift({ ...item, id: Date.now(), timestamp: new Date().toISOString() })
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_ITEMS)))
  } catch {
    // localStorage может быть недоступен
  }
}

export function clearHistory() {
  localStorage.removeItem(HISTORY_KEY)
}

export function deleteHistoryItem(id) {
  const history = getHistory().filter((h) => h.id !== id)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history))
}
