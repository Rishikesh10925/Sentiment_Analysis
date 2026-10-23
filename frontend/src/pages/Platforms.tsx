import { Navigate } from 'react-router-dom'

/** Deprecated v1 route. Platform comparison now lives on the overview. */
export function Platforms() {
  return <Navigate to="/" replace />
}
