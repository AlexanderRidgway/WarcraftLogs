import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import Layout from '../components/Layout'

function EditableTarget({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value))

  if (!editing) {
    return (
      <span onClick={() => { setEditing(true); setDraft(String(value)) }} style={{ cursor: 'pointer', borderBottom: '1px dashed #58a6ff' }}>
        {value}
      </span>
    )
  }

  return (
    <span>
      <input
        type="number"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter') { onSave(Number(draft)); setEditing(false) }
          if (e.key === 'Escape') setEditing(false)
        }}
        autoFocus
        style={{ width: 60, padding: '2px 4px', background: '#0d1117', border: '1px solid #58a6ff', borderRadius: 4, color: '#e0e0e0', fontSize: 13 }}
      />
      <button onClick={() => { onSave(Number(draft)); setEditing(false) }} style={{ marginLeft: 4, padding: '2px 8px', background: '#238636', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Save</button>
      <button onClick={() => setEditing(false)} style={{ marginLeft: 2, padding: '2px 8px', background: '#21262d', color: '#8b949e', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Cancel</button>
    </span>
  )
}

function EditableWeights({ specKey, profile, onSave }: { specKey: string; profile: any; onSave: (w: any) => void }) {
  const [editing, setEditing] = useState(false)
  const [parse, setParse] = useState(String((profile.parse_weight * 100).toFixed(0)))
  const [utility, setUtility] = useState(String((profile.utility_weight * 100).toFixed(0)))
  const [consumables, setConsumables] = useState(String(((profile.consumables_weight || 0) * 100).toFixed(0)))

  if (!editing) {
    return (
      <span onClick={() => setEditing(true)} style={{ cursor: 'pointer', borderBottom: '1px dashed #58a6ff', fontSize: 12, color: '#8b949e', marginLeft: '1rem' }}>
        parse: {(profile.parse_weight * 100).toFixed(0)}% | utility: {(profile.utility_weight * 100).toFixed(0)}% | consumables: {((profile.consumables_weight || 0) * 100).toFixed(0)}%
      </span>
    )
  }

  const handleSave = () => {
    const p = Number(parse) / 100
    const u = Number(utility) / 100
    const c = Number(consumables) / 100
    if (Math.abs(p + u + c - 1.0) > 0.01) {
      alert('Weights must sum to 100%')
      return
    }
    onSave({ parse_weight: p, utility_weight: u, consumables_weight: c })
    setEditing(false)
  }

  const inputStyle = { width: 40, padding: '2px 4px', background: '#0d1117', border: '1px solid #58a6ff', borderRadius: 4, color: '#e0e0e0', fontSize: 12, marginRight: 2 }

  return (
    <span style={{ fontSize: 12, marginLeft: '1rem' }}>
      parse: <input type="number" value={parse} onChange={e => setParse(e.target.value)} style={inputStyle} />%
      {' '}utility: <input type="number" value={utility} onChange={e => setUtility(e.target.value)} style={inputStyle} />%
      {' '}consumables: <input type="number" value={consumables} onChange={e => setConsumables(e.target.value)} style={inputStyle} />%
      <button onClick={handleSave} style={{ marginLeft: 6, padding: '2px 8px', background: '#238636', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Save</button>
      <button onClick={() => setEditing(false)} style={{ marginLeft: 2, padding: '2px 8px', background: '#21262d', color: '#8b949e', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Cancel</button>
    </span>
  )
}

export default function Config() {
  const queryClient = useQueryClient()
  const { data: specs } = useQuery({ queryKey: ['config-specs'], queryFn: api.config.specs })
  const { data: consumables } = useQuery({ queryKey: ['config-consumables'], queryFn: api.config.consumables })
  const { data: attendance } = useQuery({ queryKey: ['config-attendance'], queryFn: api.config.attendance })
  const { data: gear } = useQuery({ queryKey: ['config-gear'], queryFn: api.config.gear })

  const updateTarget = useMutation({
    mutationFn: ({ specKey, metric, target }: { specKey: string; metric: string; target: number }) =>
      api.config.updateTarget(specKey, metric, target),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-specs'] }),
  })

  const updateWeights = useMutation({
    mutationFn: ({ specKey, weights }: { specKey: string; weights: any }) =>
      api.config.updateWeights(specKey, weights),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-specs'] }),
  })

  const updateAttendance = useMutation({
    mutationFn: ({ zoneId, required }: { zoneId: number; required: number }) =>
      api.config.updateAttendance(zoneId, required),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['config-attendance'] }),
  })

  return (
    <Layout>
      <h1 style={{ marginBottom: '1.5rem' }}>Configuration</h1>

      <h2>Spec Profiles</h2>
      <p style={{ color: '#8b949e', fontSize: 13, marginBottom: '0.5rem' }}>Click values to edit. Weights must sum to 100%.</p>
      <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {specs && Object.entries(specs).map(([key, profile]: [string, any]) => (
          <div key={key} style={{ padding: '0.75rem', background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
            <strong style={{ textTransform: 'capitalize' }}>{key.replace(':', ' — ')}</strong>
            <EditableWeights
              specKey={key}
              profile={profile}
              onSave={(weights) => updateWeights.mutate({ specKey: key, weights })}
            />
            {profile.contributions?.map((c: any) => (
              <div key={c.metric} style={{ fontSize: 13, marginLeft: '1rem', color: '#8b949e' }}>
                {c.label} — target:{' '}
                <EditableTarget
                  value={c.target}
                  onSave={(target) => updateTarget.mutate({ specKey: key, metric: c.metric, target })}
                />{' '}
                ({c.type})
              </div>
            ))}
          </div>
        ))}
      </div>

      <h2>Consumables</h2>
      <div style={{ marginBottom: '1.5rem' }}>
        {consumables?.map((c: any) => (
          <div key={c.metric} style={{ fontSize: 14, padding: '0.25rem 0' }}>
            {c.label} — target: {c.target} {c.optional ? <span style={{ color: '#8b949e' }}>(optional)</span> : ''}
          </div>
        ))}
      </div>

      <h2>Attendance Requirements</h2>
      <p style={{ color: '#8b949e', fontSize: 13, marginBottom: '0.5rem' }}>Click required count to edit.</p>
      <div style={{ marginBottom: '1.5rem' }}>
        {attendance?.map((a: any) => (
          <div key={a.zone_id} style={{ fontSize: 14, padding: '0.25rem 0' }}>
            {a.label} —{' '}
            <EditableTarget
              value={a.required_per_week}
              onSave={(required) => updateAttendance.mutate({ zoneId: a.zone_id, required })}
            />x per week
          </div>
        ))}
      </div>

      <h2>Gear Check</h2>
      {gear && (
        <pre style={{ background: '#161b22', padding: '1rem', borderRadius: 8, fontSize: 13, border: '1px solid #30363d', overflow: 'auto' }}>
          {JSON.stringify(gear, null, 2)}
        </pre>
      )}
    </Layout>
  )
}
