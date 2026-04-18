import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'

export function useComplaintsRealtime() {
  const [complaints, setComplaints] = useState([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    // supabase client is module-level stable — no deps needed
    const channel = supabase
      .channel('public:complaints')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'complaints' },
        (payload) => {
          setComplaints(prev => [payload.new, ...prev])
        }
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'complaints' },
        (payload) => {
          setComplaints(prev =>
            prev.map(c => (c.id === payload.new.id ? payload.new : c))
          )
        }
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'complaints' },
        (payload) => {
          setComplaints(prev => prev.filter(c => c.id !== payload.old.id))
        }
      )
      .subscribe((status) => {
        setIsConnected(status === 'SUBSCRIBED')
      })

    return () => {
      supabase.removeChannel(channel)
    }
  }, []) // supabase client is stable — [] is intentional

  return { complaints, setComplaints, isConnected }
}
