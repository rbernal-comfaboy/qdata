import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { Shield, Plus, Trash2, Pencil, X, Check, FolderPlus, Settings2, Eye, Save } from 'lucide-react'
import api from '../api/client'
import GlassContainer from '../components/layout/GlassContainer'

const SEVERITY_COLORS: Record<string, string> = {
  error: 'bg-red-500/20 text-red-300 border-red-500/30',
  warning: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  info: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
}

export default function Rules() {
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [editingRule, setEditingRule] = useState<any>(null)
  const [viewingRule, setViewingRule] = useState<any>(null)
  const [editForm, setEditForm] = useState({ name: '', description: '', rule_type: 'sql', rule_code: '', severity: 'error', group: 'custom' })
  const [showGroupManager, setShowGroupManager] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupLabel, setNewGroupLabel] = useState('')
  const [editGroupId, setEditGroupId] = useState<string | null>(null)
  const [editGroupLabel, setEditGroupLabel] = useState('')

  const anyModalOpen = editingRule || viewingRule || showGroupManager
  useEffect(() => {
    if (!anyModalOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setEditingRule(null)
        setViewingRule(null)
        setShowGroupManager(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [anyModalOpen])

  const { data: groupsData } = useQuery({
    queryKey: ['rules-groups'],
    queryFn: () => api.get('/rules/groups').then((r) => r.data),
  })

  const { data: groupManageData } = useQuery({
    queryKey: ['groups-manage'],
    queryFn: () => api.get('/rules/groups/manage').then((r) => r.data),
  })

  const { data: customRules } = useQuery({
    queryKey: ['custom-rules'],
    queryFn: () => api.get('/rules/custom').then((r) => r.data),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => api.post('/rules/custom', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
      setShowNew(false)
      setEditForm({ name: '', description: '', rule_type: 'sql', rule_code: '', severity: 'error', group: 'custom' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.put(`/rules/custom/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
      setEditingRule(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/rules/custom/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-rules'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
    },
  })

  const createGroupMutation = useMutation({
    mutationFn: (data: any) => api.post('/rules/groups/manage', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups-manage'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
      setNewGroupName('')
      setNewGroupLabel('')
    },
  })

  const updateGroupMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.put(`/rules/groups/manage/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups-manage'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
      setEditGroupId(null)
    },
  })

  const deleteGroupMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/rules/groups/manage/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups-manage'] })
      queryClient.invalidateQueries({ queryKey: ['rules-groups'] })
    },
  })

  const allGroups = groupsData?.groups ?? []

  const startEdit = (rule: any) => {
    setEditForm({
      name: rule.name,
      description: rule.description || '',
      rule_type: rule.rule_type || 'sql',
      rule_code: rule.rule_code || '',
      severity: rule.severity || 'error',
      group: rule.group || 'custom',
    })
    setEditingRule(rule)
  }

  const startView = (rule: any) => {
    setViewingRule(rule)
  }

  const flatRules = allGroups
    .filter((g: any) => g.name !== 'todo')
    .flatMap((g: any) =>
      g.rules.map((r: any) => ({ ...r, groupLabel: g.label, groupName: g.name, isCustom: false }))
    )

  const customFlat = (customRules || []).map((r: any) => ({
    ...r,
    label: r.name,
    groupLabel: allGroups.find((g: any) => g.name === r.group)?.label || 'Sin categoría',
    groupName: r.group,
    isCustom: true,
  }))

  const allRules = [...flatRules, ...customFlat]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">Reglas de Validación</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowGroupManager(true)} className="btn-ghost flex items-center gap-2">
            <FolderPlus className="w-4 h-4" /> Grupos
          </button>
          <button onClick={() => {
            setShowNew(!showNew)
            setEditForm({ name: '', description: '', rule_type: 'sql', rule_code: '', severity: 'error', group: 'custom' })
          }} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Nueva Regla
          </button>
        </div>
      </div>

      {showNew && (
        <GlassContainer className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Crear Regla Personalizada</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-muted mb-1">Nombre</label>
              <input type="text" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                className="glass-input" placeholder="Mi regla" />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Tipo</label>
              <select value={editForm.rule_type} onChange={(e) => setEditForm({ ...editForm, rule_type: e.target.value })}
                className="glass-input">
                <option value="sql">SQL</option>
                <option value="python">Python</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Grupo / Categoría</label>
              <select value={editForm.group} onChange={(e) => setEditForm({ ...editForm, group: e.target.value })}
                className="glass-input">
                <option value="custom">Sin categoría</option>
                {allGroups.filter((g: any) => g.name !== 'todo').map((g: any) => (
                  <option key={g.name} value={g.name}>{g.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">Severidad</label>
              <select value={editForm.severity} onChange={(e) => setEditForm({ ...editForm, severity: e.target.value })}
                className="glass-input">
                <option value="error">Error</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-muted mb-1">Descripción</label>
              <input type="text" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                className="glass-input" placeholder="Describe qué valida esta regla" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-muted mb-1">Código</label>
              <textarea value={editForm.rule_code} onChange={(e) => setEditForm({ ...editForm, rule_code: e.target.value })}
                className="glass-input font-mono text-sm min-h-[120px]"
                placeholder={editForm.rule_type === 'sql' ? 'SELECT * FROM data WHERE columna IS NULL' : 'def validate(df):\n  return df["columna"].notna()'} />
            </div>
          </div>
          <button onClick={() => createMutation.mutate(editForm)}
            className="btn-primary">Guardar Regla</button>
        </GlassContainer>
      )}

      <GlassContainer>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-muted">
                <th className="text-left py-3 px-4 font-medium">Regla</th>
                <th className="text-left py-3 px-4 font-medium">Grupo</th>
                <th className="text-left py-3 px-4 font-medium">Severidad</th>
                <th className="text-left py-3 px-4 font-medium hidden md:table-cell">Descripción</th>
                <th className="text-right py-3 px-4 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {allRules.map((rule: any) => (
                <tr key={rule.name + (rule.isCustom ? '-custom' : '')} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <Shield className={`w-4 h-4 shrink-0 ${rule.isCustom ? 'text-yellow-400' : 'text-indigo-400'}`} />
                      <span className="font-medium">{rule.label}</span>
                      {rule.isCustom && <span className="text-xs text-yellow-400 bg-yellow-500/10 px-1.5 py-0.5 rounded">personalizada</span>}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-muted">{rule.groupLabel}</td>
                  <td className="py-3 px-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[rule.severity] || ''}`}>
                      {rule.severity}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-muted text-xs hidden md:table-cell max-w-xs truncate">{rule.description}</td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => startView(rule)} className="p-1.5 hover:bg-white/10 rounded text-muted hover:text-white transition-colors" title="Ver">
                        <Eye className="w-4 h-4" />
                      </button>
                      {rule.isCustom && (
                        <>
                          <button onClick={() => startEdit(rule)} className="p-1.5 hover:bg-white/10 rounded text-muted hover:text-indigo-300 transition-colors" title="Editar">
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button onClick={() => deleteMutation.mutate(rule.id)} className="p-1.5 hover:bg-white/10 rounded text-muted hover:text-red-300 transition-colors" title="Eliminar">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {allRules.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-muted">No hay reglas disponibles</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassContainer>

      {editingRule && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={(e) => { if (e.target === e.currentTarget) setEditingRule(null) }}>
          <GlassContainer className="w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">Editar Regla</h2>
              <button onClick={() => setEditingRule(null)} className="p-1 hover:bg-white/10 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm text-muted mb-1">Nombre</label>
                <input type="text" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="glass-input" />
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Tipo</label>
                <select value={editForm.rule_type} onChange={(e) => setEditForm({ ...editForm, rule_type: e.target.value })}
                  className="glass-input">
                  <option value="sql">SQL</option>
                  <option value="python">Python</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Grupo</label>
                <select value={editForm.group} onChange={(e) => setEditForm({ ...editForm, group: e.target.value })}
                  className="glass-input">
                  <option value="custom">Sin categoría</option>
                  {allGroups.filter((g: any) => g.name !== 'todo').map((g: any) => (
                    <option key={g.name} value={g.name}>{g.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">Severidad</label>
                <select value={editForm.severity} onChange={(e) => setEditForm({ ...editForm, severity: e.target.value })}
                  className="glass-input">
                  <option value="error">Error</option>
                  <option value="warning">Warning</option>
                  <option value="info">Info</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm text-muted mb-1">Descripción</label>
                <input type="text" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  className="glass-input" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm text-muted mb-1">Código</label>
                <textarea value={editForm.rule_code} onChange={(e) => setEditForm({ ...editForm, rule_code: e.target.value })}
                  className="glass-input font-mono text-sm min-h-[120px]" />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditingRule(null)} className="btn-ghost">Cancelar</button>
              <button onClick={() => updateMutation.mutate({ id: editingRule.id, data: editForm })}
                className="btn-primary flex items-center gap-2">
                <Save className="w-4 h-4" /> Guardar Cambios
              </button>
            </div>
          </GlassContainer>
        </div>
      )}

      {viewingRule && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={(e) => { if (e.target === e.currentTarget) setViewingRule(null) }}>
          <GlassContainer className="w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Shield className={`w-5 h-5 ${viewingRule.isCustom ? 'text-yellow-400' : 'text-indigo-400'}`} />
                {viewingRule.label}
              </h2>
              <button onClick={() => setViewingRule(null)} className="p-1 hover:bg-white/10 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex gap-4">
                <div>
                  <span className="text-muted text-xs">Grupo</span>
                  <p className="font-medium">{viewingRule.groupLabel}</p>
                </div>
                <div>
                  <span className="text-muted text-xs">Severidad</span>
                  <p><span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_COLORS[viewingRule.severity] || ''}`}>{viewingRule.severity}</span></p>
                </div>
              </div>
              <div>
                <span className="text-muted text-xs">Descripción</span>
                <p>{viewingRule.description || 'Sin descripción'}</p>
              </div>
              {viewingRule.groupName && (
                <div>
                  <span className="text-muted text-xs">Nombre interno</span>
                  <p><code className="text-xs bg-white/5 px-1.5 py-0.5 rounded">{viewingRule.name}</code></p>
                </div>
              )}
              {viewingRule.rule_code && (
                <div>
                  <span className="text-muted text-xs">Código</span>
                  <pre className="bg-white/5 rounded-lg p-3 font-mono text-xs mt-1 overflow-x-auto">{viewingRule.rule_code}</pre>
                </div>
              )}
              {viewingRule.isCustom && (
                <button onClick={() => { setViewingRule(null); startEdit(viewingRule) }}
                  className="btn-primary flex items-center gap-2 mt-4">
                  <Pencil className="w-4 h-4" /> Editar Regla
                </button>
              )}
            </div>
          </GlassContainer>
        </div>
      )}

      {showGroupManager && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={(e) => { if (e.target === e.currentTarget) setShowGroupManager(false) }}>
          <GlassContainer className="w-full max-w-lg max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Settings2 className="w-5 h-5" /> Gestionar Grupos
              </h2>
              <button onClick={() => setShowGroupManager(false)} className="p-1 hover:bg-white/10 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex gap-2 mb-4">
              <input type="text" value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)}
                className="glass-input flex-1" placeholder="nombre (ej: calidad)" />
              <input type="text" value={newGroupLabel} onChange={(e) => setNewGroupLabel(e.target.value)}
                className="glass-input flex-1" placeholder="Etiqueta (ej: Calidad)" />
              <button onClick={() => createGroupMutation.mutate({ name: newGroupName, label: newGroupLabel })}
                disabled={!newGroupName || !newGroupLabel}
                className="btn-primary disabled:opacity-50">
                <Check className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2">
              {groupManageData?.map((g: any) => (
                <div key={g.id || g.name} className="flex items-center justify-between bg-white/5 rounded-lg p-3">
                  {editGroupId === g.id ? (
                    <div className="flex items-center gap-2 flex-1">
                      <input type="text" value={editGroupLabel} onChange={(e) => setEditGroupLabel(e.target.value)}
                        className="glass-input flex-1" />
                      <button onClick={() => updateGroupMutation.mutate({ id: g.id, data: { label: editGroupLabel } })}
                        className="text-green-400 p-1"><Check className="w-4 h-4" /></button>
                      <button onClick={() => setEditGroupId(null)} className="text-muted p-1"><X className="w-4 h-4" /></button>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{g.label}</span>
                        <code className="text-xs text-muted bg-white/5 px-1.5 py-0.5 rounded">{g.name}</code>
                        {g.is_builtin && <span className="text-xs text-muted bg-white/5 px-1.5 py-0.5 rounded">built-in</span>}
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => { setEditGroupId(g.id); setEditGroupLabel(g.label) }}
                          className="text-indigo-400 hover:text-indigo-300 p-1 disabled:opacity-30" disabled={g.is_builtin}>
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => deleteGroupMutation.mutate(g.id)}
                          className="text-red-400 hover:text-red-300 p-1 disabled:opacity-30" disabled={g.is_builtin}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </GlassContainer>
        </div>
      )}
    </div>
  )
}
