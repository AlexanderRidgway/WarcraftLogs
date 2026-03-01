import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { CHART_COLORS, CHART_DEFAULTS } from './ChartTheme'
import type { TrendPoint } from '../api/types'

export default function TrendChart({ data }: { data: TrendPoint[] }) {
  const formatted = data.map(d => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  const hasUtility = data.some(d => d.utility_score !== null)

  return (
    <div className="bg-bg-surface border border-border-default rounded-xl p-4 mb-4">
      <h3 className="text-sm font-semibold text-text-primary mb-3">Score Trends</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={formatted}>
          <CartesianGrid stroke={CHART_DEFAULTS.gridStroke} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
          <YAxis domain={[0, 100]} tick={CHART_DEFAULTS.tick} axisLine={CHART_DEFAULTS.axisLine} />
          <Tooltip
            contentStyle={{ backgroundColor: CHART_COLORS.bg, border: `1px solid ${CHART_COLORS.grid}`, borderRadius: 8 }}
            labelStyle={{ color: CHART_COLORS.text }}
          />
          <Legend wrapperStyle={{ color: CHART_COLORS.text }} />
          <Line type="monotone" dataKey="overall_score" name="Overall" stroke={CHART_COLORS.gold} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="parse_score" name="Parse" stroke={CHART_COLORS.info} strokeWidth={2} dot={false} />
          {hasUtility && (
            <Line type="monotone" dataKey="utility_score" name="Utility" stroke={CHART_COLORS.success} strokeWidth={2} dot={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
