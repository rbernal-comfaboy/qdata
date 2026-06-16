import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Clock, Mail, Calendar, ArrowLeft } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

const freqLabels: Record<string, string> = {
  once: 'Una vez',
  daily: 'Cada día',
  weekly: 'Cada semana',
  monthly: 'Cada mes',
  yearly: 'Cada año',
}

const weekdayLabels: Record<string, string> = {
  '0': 'Domingo', '1': 'Lunes', '2': 'Martes', '3': 'Miércoles',
  '4': 'Jueves', '5': 'Viernes', '6': 'Sábado',
}

export default function SchedulerNew() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preselected = searchParams.get('project') || ''
  const [name, setName] = useState('')
  const [projectId, setProjectId] = useState(preselected)
  const [freq, setFreq] = useState('daily')
  const [hour, setHour] = useState('8')
  const [minute, setMinute] = useState('0')
  const [weekday, setWeekday] = useState('1')
  const [monthDay, setMonthDay] = useState('1')
  const [notifyEmails, setNotifyEmails] = useState('')

  const { data: processes } = useQuery({
    queryKey: ['processes'],
    queryFn: () => api.get('/processes').then((r) => r.data),
  })

  const mutation = useMutation({
    mutationFn: (data: any) => api.post('/scheduler/tasks', data),
    onSuccess: () => navigate('/scheduler'),
  })

  const buildCron = () => {
    const h = hour.padStart(2, '0')
    const m = minute.padStart(2, '0')
    switch (freq) {
      case 'once': return `${m} ${h} ${new Date().getDate()} ${new Date().getMonth() + 1} *`
      case 'daily': return `${m} ${h} * * *`
      case 'weekly': return `${m} ${h} * * ${weekday}`
      case 'monthly': return `${m} ${h} ${monthDay} * *`
      case 'yearly': return `${m} ${h} ${monthDay} 1 *`
      default: return `${m} ${h} * * *`
    }
  }

  const getFreqDescription = () => {
    switch (freq) {
      case 'once': return `Se ejecutará una vez hoy a las ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      case 'daily': return `Se ejecutará todos los días a las ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      case 'weekly': return `Se ejecutará los ${weekdayLabels[weekday]?.toLowerCase()} a las ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      case 'monthly': return `Se ejecutará el día ${monthDay} de cada mes a las ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      case 'yearly': return `Se ejecutará el ${monthDay} de enero cada año a las ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
      default: return ''
    }
  }

  const handleSubmit = () => {
    mutation.mutate({
      project_id: projectId,
      name,
      cron_expr: buildCron(),
      notify_emails: notifyEmails.split(',').map((e) => e.trim()).filter(Boolean),
    })
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/scheduler')} className="btn-ghost p-2">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-3xl font-bold">Nueva Tarea Programada</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GlassContainer>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Configuración
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-muted mb-1">Nombre de la tarea</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                className="glass-input" placeholder="Ej: Análisis diario de ventas" />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Proceso de análisis</label>
              <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="glass-input">
                <option value="">Seleccionar proceso...</option>
                {(processes || []).map((p: any) => (
                  <option key={p.id} value={p.id}>
                    {p.name} {p.latest_report ? `(Score: ${p.latest_report.score})` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </GlassContainer>

        <GlassContainer>
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Programación
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-muted mb-2">Frecuencia</label>
              <div className="grid grid-cols-5 gap-2">
                {Object.entries(freqLabels).map(([k, v]) => (
                  <button key={k} onClick={() => setFreq(k)}
                    className={`text-xs py-2 px-1 rounded-lg border transition-all ${
                      freq === k
                        ? 'bg-indigo-500/20 border-indigo-400 text-white'
                        : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                    }`}>
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-1">
                <label className="block text-sm text-muted mb-1">Hora</label>
                <select value={hour} onChange={(e) => setHour(e.target.value)} className="glass-input">
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={String(i)}>{String(i).padStart(2, '0')}:00</option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-sm text-muted mb-1">Minuto</label>
                <select value={minute} onChange={(e) => setMinute(e.target.value)} className="glass-input">
                  {Array.from({ length: 12 }, (_, i) => (
                    <option key={i} value={String(i * 5)}>{String(i * 5).padStart(2, '0')}</option>
                  ))}
                </select>
              </div>
            </div>

            {freq === 'weekly' && (
              <div>
                <label className="block text-sm text-muted mb-2">Día de la semana</label>
                <div className="grid grid-cols-7 gap-2">
                  {Object.entries(weekdayLabels).map(([k, v]) => (
                    <button key={k} onClick={() => setWeekday(k)}
                      className={`text-xs py-2 rounded-lg border transition-all ${
                        weekday === k
                          ? 'bg-indigo-500/20 border-indigo-400 text-white'
                          : 'bg-white/5 border-white/10 text-muted hover:bg-white/10'
                      }`}>
                      {v.slice(0, 3)}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {(freq === 'monthly' || freq === 'yearly') && (
              <div>
                <label className="block text-sm text-muted mb-1">Día del mes</label>
                <select value={monthDay} onChange={(e) => setMonthDay(e.target.value)} className="glass-input">
                  {Array.from({ length: 28 }, (_, i) => (
                    <option key={i + 1} value={String(i + 1)}>{i + 1}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-lg p-3 text-sm text-indigo-300 text-center">
              {getFreqDescription()}
            </div>

            <div className="text-xs text-muted text-center">
              Cron: <span className="font-mono text-indigo-300">{buildCron()}</span>
            </div>
          </div>
        </GlassContainer>

        <GlassContainer className="lg:col-span-2">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Mail className="w-5 h-5" />
            Notificaciones por Email
          </h2>
          <div>
            <label className="block text-sm text-muted mb-1">
              Correos destinatarios (separados por coma)
            </label>
            <input type="text" value={notifyEmails} onChange={(e) => setNotifyEmails(e.target.value)}
              className="glass-input" placeholder="analista@empresa.com, jefe@empresa.com" />
          </div>
        </GlassContainer>
      </div>

      <div className="mt-6 flex justify-end gap-4">
        <button onClick={() => navigate('/scheduler')} className="btn-ghost">
          Cancelar
        </button>
        <button
          onClick={handleSubmit}
          disabled={!name || !projectId || mutation.isPending}
          className="btn-primary disabled:opacity-50"
        >
          {mutation.isPending ? 'Creando...' : 'Crear Tarea'}
        </button>
      </div>
    </div>
  )
}
