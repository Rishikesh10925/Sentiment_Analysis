import { Navigate } from 'react-router-dom'

/** Deprecated v1 route. Topic analysis now lives on the overview. */
export function Topics() {
  return <Navigate to="/" replace />
}
