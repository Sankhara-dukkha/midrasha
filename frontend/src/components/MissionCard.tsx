import { Link } from 'react-router-dom'
import type { MissionInstance } from '../api/types'

const STATUS_LABEL: Record<MissionInstance['status'], string> = {
  assigned: 'Assigned',
  in_progress: 'In progress',
  completed: 'Completed',
  failed: 'Failed',
}

export function MissionCard({ mission }: { mission: MissionInstance }) {
  const { template } = mission
  return (
    <article className="card">
      <header>
        <span className={`tag tag-${template.type}`}>{template.type}</span>
        <span className={`status status-${mission.status}`}>{STATUS_LABEL[mission.status]}</span>
      </header>
      {/* dir="auto" lets Hebrew/Arabic/Farsi text render right-to-left. */}
      <h3 dir="auto">{template.name}</h3>
      <p dir="auto">{template.description}</p>
      <Link to={`/mission/${mission.id}`} className="button">
        Open mission
      </Link>
    </article>
  )
}
