import { Link, useParams } from 'react-router-dom'
import { api } from '../api/endpoints'
import { useAsync } from '../hooks/useAsync'

export function MissionDetail() {
  const { id = '' } = useParams()
  const { data: mission, error, loading } = useAsync(() => api.mission(id), [id])

  if (loading) return <p className="muted">Decrypting mission file…</p>
  if (error || !mission) return <p className="error">Mission not found.</p>

  const { template } = mission
  return (
    <section>
      <Link to="/dashboard">← Back to briefing</Link>
      <h1 dir="auto">{template.name}</h1>
      <p className="muted">
        {template.type} · difficulty {template.difficulty}/5 · {mission.status}
      </p>
      <p dir="auto">{template.description}</p>
      {/* Linked resources, completion logging and recruiter audio arrive in later increments. */}
    </section>
  )
}
