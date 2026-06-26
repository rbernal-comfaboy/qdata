import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

interface QualityGaugeProps {
  score: number
  size?: number
}

export default function QualityGauge({ score, size = 200 }: QualityGaugeProps) {
  const data = [
    { name: 'Score', value: score },
    { name: 'Rest', value: 100 - score },
  ]

  const getColor = (s: number) => {
    if (s >= 90) return '#48bb78'
    if (s >= 70) return '#f6ad55'
    if (s >= 50) return '#ed8936'
    return '#f56565'
  }

  return (
    <div className="relative inline-flex items-center justify-center">
      <ResponsiveContainer width={size} height={size}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={size * 0.32}
            outerRadius={size * 0.45}
            startAngle={180}
            endAngle={-180}
            dataKey="value"
            stroke="none"
          >
            <Cell fill={getColor(score)} />
            <Cell fill="rgba(255,255,255,0.08)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-bold text-white" style={{ fontSize: size * 0.15 }}>
          {Number(score).toFixed(2)}%
        </span>
      </div>
    </div>
  )
}
