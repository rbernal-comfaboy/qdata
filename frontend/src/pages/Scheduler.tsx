import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Clock, Plus, Play, Pause, Trash2, AlertTriangle } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'
import { formatDate } from '../lib/utils'

export default function Scheduler() {
  const queryClient = useQueryClient()
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false)

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['scheduler-tasks'],
    queryFn: () => api.get('/scheduler/tasks').then((r) => r.data),
  })

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post(`/scheduler/tasks/${id}/run`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduler-tasks'] }),
  })

  const pauseMutation = useMutation({
    mutationFn: (id: string) => api.post(`/scheduler/tasks/${id}/pause`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduler-tasks'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/scheduler/tasks/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scheduler-tasks'] }),
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Error al eliminar la tarea')
    },
  })

  const deleteAllMutation = useMutation({
    mutationFn: () => api.delete('/scheduler/tasks'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler-tasks'] })
      setConfirmDeleteAll(false)
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Error al eliminar las tareas')
    },
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-white">Programador de Tareas</h1>
        <div className="flex items-center gap-2">
          {tasks?.length > 0 && !confirmDeleteAll && (
            <button onClick={() => setConfirmDeleteAll(true)} className="btn-ghost flex items-center gap-2 text-red-400 text-sm">
              <Trash2 className="w-4 h-4" />
              Borrar todas
            </button>
          )}
          {confirmDeleteAll && (
            <div className="flex items-center gap-2 bg-red-500/20 border border-red-500/30 rounded-xl px-3 py-1.5">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-sm text-red-300">¿Eliminar todas?</span>
              <button onClick={() => deleteAllMutation.mutate()} disabled={deleteAllMutation.isPending}
                className="btn-ghost text-xs text-red-400 font-semibold px-2">
                {deleteAllMutation.isPending ? 'Eliminando...' : 'Sí'}
              </button>
              <button onClick={() => setConfirmDeleteAll(false)} className="btn-ghost text-xs text-muted px-2">
                No
              </button>
            </div>
          )}
          <Link to="/scheduler/new" className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Nueva Tarea
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2].map((i) => <div key={i} className="skeleton h-24 rounded-xl" />)}
        </div>
      ) : tasks?.length > 0 ? (
        <div className="space-y-4">
          {tasks.map((task: any) => (
            <GlassContainer key={task.id} className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Clock className={`w-8 h-8 ${task.status === 'active' ? 'text-green-400' : 'text-yellow-400'}`} />
                <div>
                  <p className="text-white font-medium">{task.name}</p>
                  <div className="flex items-center gap-3 text-xs text-muted mt-1">
                    <span className="font-mono">{task.cron_expr}</span>
                    <span>|</span>
                    <span>Última: {task.last_run ? formatDate(task.last_run) : 'Nunca'}</span>
                    {task.error_count > 0 && (
                      <>
                        <span>|</span>
                        <span className="text-red-400">{task.error_count} errores</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`badge ${task.status === 'active' ? 'badge-success' : 'badge-warning'}`}>
                  {task.status}
                </span>
                <button
                  onClick={() => runMutation.mutate(task.id)}
                  className="btn-ghost p-2"
                  title="Ejecutar ahora"
                >
                  <Play className="w-4 h-4" />
                </button>
                <button
                  onClick={() => pauseMutation.mutate(task.id)}
                  className="btn-ghost p-2"
                  title="Pausar/Reanudar"
                >
                  <Pause className="w-4 h-4" />
                </button>
                <button
                  onClick={() => deleteMutation.mutate(task.id)}
                  className="btn-ghost p-2 text-red-400"
                  title="Eliminar"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </GlassContainer>
          ))}
        </div>
      ) : (
        <GlassContainer className="text-center py-12">
          <Clock className="w-12 h-12 mx-auto mb-4 text-muted" />
          <p className="text-muted mb-4">No hay tareas programadas</p>
          <Link to="/scheduler/new" className="btn-primary inline-block">
            Crear primera tarea
          </Link>
        </GlassContainer>
      )}
    </div>
  )
}
