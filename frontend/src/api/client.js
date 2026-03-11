const BASE_URL = '/api/v1'

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ─── Evaluator ────────────────────────────────────────────────────────────────

export const evaluateGoal = (data) =>
  request('/evaluate', { method: 'POST', body: JSON.stringify(data) })

export const reformulateGoal = (data) =>
  request('/reformulate', { method: 'POST', body: JSON.stringify(data) })

export const evaluateBatch = (data) =>
  request('/evaluate/batch', { method: 'POST', body: JSON.stringify(data) })

// ─── Generator ────────────────────────────────────────────────────────────────

export const generateGoals = (data) =>
  request('/generate', { method: 'POST', body: JSON.stringify(data) })

// ─── Analytics ────────────────────────────────────────────────────────────────

export const getDashboard = (quarter) =>
  request(`/analytics/dashboard${quarter ? `?quarter=${quarter}` : ''}`)

export const getTrends = (departmentId) =>
  request(`/analytics/trends${departmentId ? `?department_id=${departmentId}` : ''}`)

export const getDepartmentAnalytics = (deptId, quarter) =>
  request(`/analytics/department/${deptId}${quarter ? `?quarter=${quarter}` : ''}`)

// ─── Documents ────────────────────────────────────────────────────────────────

export const searchDocuments = (data) =>
  request('/documents/search', { method: 'POST', body: JSON.stringify(data) })

// ─── Employees ────────────────────────────────────────────────────────────────

export const getEmployees = (search, departmentId) => {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (departmentId) params.set('department_id', departmentId)
  return request(`/employees?${params}`)
}

export const getEmployee = (id) => request(`/employees/${id}`)

export const getEmployeeGoals = (id, quarter) =>
  request(`/employees/${id}/goals${quarter ? `?quarter=${quarter}` : ''}`)

export const getDepartments = () => request('/departments')

export const getDepartmentKpi = (deptId) => request(`/kpi/${deptId}`)
