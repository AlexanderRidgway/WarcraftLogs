import { useAuth } from '../contexts/AuthContext'

/**
 * Feature flag: when true, all performance score data is hidden
 * behind officer authentication. Set to false to make scores
 * visible to everyone again.
 */
const SCORES_OFFICER_ONLY = true

export function useScoreAccess() {
  const { isAuthenticated } = useAuth()
  return {
    canViewScores: SCORES_OFFICER_ONLY ? isAuthenticated : true,
  }
}
