import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'

const CRITERION_LABELS = { S: 'Specific', M: 'Measurable', A: 'Achievable', R: 'Relevant', T: 'Time-bound' }

function buildData(smart) {
  if (!smart) return []
  // Плоский формат SmartScores (specific/measurable/achievable/relevant/time_bound)
  if (smart.specific !== undefined) {
    return [
      { criterion: 'S', label: 'Specific', score: smart.specific ?? 0 },
      { criterion: 'M', label: 'Measurable', score: smart.measurable ?? 0 },
      { criterion: 'A', label: 'Achievable', score: smart.achievable ?? 0 },
      { criterion: 'R', label: 'Relevant', score: smart.relevant ?? 0 },
      { criterion: 'T', label: 'Time-bound', score: smart.time_bound ?? 0 },
    ]
  }
  // Детальный формат SmartEvaluationResult (S/M/A/R/T с .score)
  return ['S', 'M', 'A', 'R', 'T'].map((key) => ({
    criterion: key,
    label: CRITERION_LABELS[key],
    score: smart?.[key]?.score ?? 0,
  }))
}

function scoreColor(score) {
  if (score >= 0.75) return '#10b981'
  if (score >= 0.5) return '#f59e0b'
  return '#ef4444'
}

export default function SmartRadarChart({ smart, comparedSmart, size = 300 }) {
  if (!smart) return null

  const data = buildData(smart)
  const hasComparison = !!comparedSmart
  const compData = hasComparison ? buildData(comparedSmart) : null

  const mergedData = data.map((d, i) => ({
    ...d,
    original: d.score,
    ...(hasComparison ? { improved: compData[i].score } : {}),
  }))

  return (
    <ResponsiveContainer width="100%" height={size}>
      <RadarChart data={mergedData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
        <PolarGrid stroke="#e2e8f0" />
        <PolarAngleAxis
          dataKey="criterion"
          tick={({ payload, x, y, cx, cy, ...rest }) => {
            const score = mergedData.find((d) => d.criterion === payload.value)?.original ?? 0
            return (
              <g>
                <text
                  x={x}
                  y={y}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="text-xs font-bold"
                  fill="#1e3a5f"
                  fontSize={13}
                  fontWeight={700}
                >
                  {payload.value}
                </text>
                <text
                  x={x}
                  y={y + 14}
                  textAnchor="middle"
                  fill={scoreColor(score)}
                  fontSize={11}
                  fontWeight={600}
                >
                  {score.toFixed(2)}
                </text>
              </g>
            )
          }}
        />
        <PolarRadiusAxis angle={90} domain={[0, 1]} tick={false} axisLine={false} />
        <Tooltip
          formatter={(value, name) => [value.toFixed(2), name === 'original' ? 'До' : 'После']}
        />
        <Radar
          name={hasComparison ? 'До' : 'Оценка'}
          dataKey="original"
          stroke="#1e3a5f"
          fill="#1e3a5f"
          fillOpacity={hasComparison ? 0.2 : 0.4}
          strokeWidth={2}
        />
        {hasComparison && (
          <Radar
            name="После"
            dataKey="improved"
            stroke="#f59e0b"
            fill="#f59e0b"
            fillOpacity={0.35}
            strokeWidth={2}
          />
        )}
        {hasComparison && <Legend />}
      </RadarChart>
    </ResponsiveContainer>
  )
}
