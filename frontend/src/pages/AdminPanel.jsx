import { useState, useEffect, useRef, useCallback, Fragment } from 'react'
import PropTypes from 'prop-types'
import { useAuth } from '../services/AuthContext'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Legend, Cell, ResponsiveContainer } from 'recharts'
import { useComplaintsRealtime } from '../hooks/useComplaintsRealtime'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const STATUS_COLORS = {
  pending: '#F59E0B',
  assigned: '#3B82F6',
  in_progress: '#8B5CF6',
  completed: '#10B981',
  rejected: '#EF4444'
}

export default function AdminPanel() {
  const { token, isAdmin, user } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('Overview')
  const [toasts, setToasts] = useState([])

  const { complaints: realtimeComplaints, isConnected } = useComplaintsRealtime()
  const feedEndRef = useRef(null)

  useEffect(() => {
    if (!isAdmin) navigate('/')
  }, [isAdmin, navigate])

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [realtimeComplaints])

  const showToast = useCallback((msg, type = 'success') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#0d0f14', color: '#e8eaf0', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
        <div style={styles.header}>
          <div>
            <h1 style={styles.title}>Admin Panel <span style={{fontSize:12, color: isConnected?'#10b981':'#ef4444', verticalAlign: 'middle', marginLeft: 8}}>● {isConnected?'Live':'Offline'}</span></h1>
            <p style={styles.subtitle}>System configuration and personnel management</p>
          </div>
          <button onClick={() => navigate('/')} style={styles.btnOutline}>← Back to Dashboard</button>
        </div>

        <div style={styles.tabsWrap}>
          {['Overview', 'Officers'].map(tab => (
            <button
              key={tab}
              style={{ ...styles.tabBtn, borderBottomColor: activeTab === tab ? '#3B82F6' : 'transparent', color: activeTab === tab ? '#e8eaf0' : '#7a8299' }}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div style={{ paddingBottom: 60 }}>
          {activeTab === 'Overview' && <OverviewTab token={token} />}
          {activeTab === 'Officers' && <OfficersTab token={token} currentOfficerId={user?.id} showToast={showToast} />}
        </div>
      </div>

      {/* Activity Feed Sidebar */}
      <div style={{ width: 300, background: '#161a23', borderLeft: '1px solid #252b38', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid #252b38' }}>
          <h3 style={{ margin: 0, fontSize: 16 }}>Live Activity Feed</h3>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {realtimeComplaints.length === 0 ? <div style={{color: '#7a8299', fontSize: 13, textAlign: 'center', marginTop: 20}}>Waiting for live updates...</div> : null}
          {realtimeComplaints.map((e, i) => (
            <div key={i} style={{ background: '#0d0f14', padding: 12, borderRadius: 8, border: '1px solid #252b38', fontSize: 13, lineHeight: '1.4' }}>
               <span role="img" aria-label="live">📡</span> Live Update: Complaint {e.complaint_id} is now {e.status}
            </div>
          ))}
          <div ref={feedEndRef} />
        </div>
      </div>

      {/* Toasts */}
      <div style={styles.toastContainer}>
        {toasts.map(t => (
          <div key={t.id} style={{ ...styles.toast, background: t.type === 'error' ? '#EF4444' : '#10B981' }}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  )
}

function OverviewTab({ token }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${BASE_URL}/admin/stats`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json())
      .then(data => { setStats(data); setLoading(false); })
      .catch(console.error)
  }, [token])

  if (loading) return <div style={styles.loading}>Loading Overview...</div>
  if (!stats) return <div style={styles.loading}>Failed to load stats.</div>

  return (
    <div>
      <div style={styles.statsGrid}>
        <StatCard label="Total Complaints" value={stats.total_complaints} color="#7a8299" />
        <StatCard label="Open" value={stats.open} color="#3B82F6" />
        <StatCard label="Completed" value={stats.completed} color="#10B981" />
        <StatCard label="High Severity" value={stats.high_severity} color="#EF4444" />
      </div>
      <div style={{ ...styles.statsGrid, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <StatCard label="Active Officers" value={stats.active_officers} />
        <StatCard label="Complaints Today" value={stats.complaints_today} />
      </div>

      <div style={{ display: 'flex', gap: 24, marginTop: 24, flexWrap: 'wrap' }}>
        <div style={styles.chartWrap}>
          <h3 style={styles.chartTitle}>Complaints by Area Type</h3>
          <div style={{ height: 280, width: '100%' }}>
            <ResponsiveContainer>
              <BarChart data={stats.by_area || []}>
                <XAxis dataKey="area" stroke="#7a8299" fontSize={12} />
                <YAxis stroke="#7a8299" fontSize={12} />
                <Tooltip cursor={{ fill: '#252b38' }} contentStyle={{ background: '#161a23', border: '1px solid #252b38' }} />
                <Bar dataKey="count" fill="#3B82F6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div style={styles.chartWrap}>
          <h3 style={styles.chartTitle}>Complaints by Status</h3>
          <div style={{ height: 280, width: '100%' }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={stats.by_status || []} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={90}>
                  {(stats.by_status || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={STATUS_COLORS[entry.status.toLowerCase()] || '#7a8299'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#161a23', border: '1px solid #252b38' }} />
                <Legend iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color = '#f5a623' }) {
  return (
    <div style={{ ...styles.statCard, borderTop: `3px solid ${color}` }}>
      <div style={{ fontSize: 28, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 13, color: '#7a8299', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function OfficersTab({ token, currentOfficerId, showToast }) {
  const [officers, setOfficers] = useState([])
  const [loading, setLoading] = useState(true)
  const [addMode, setAddMode] = useState(false)

  // Cache for stats expansion
  const [expandedRow, setExpandedRow] = useState(null)
  const statsCache = useRef(new Map())
  const [expandedData, setExpandedData] = useState(null)

  const [editingId, setEditingId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    fetch(`${BASE_URL}/admin/officers`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.json())
      .then(d => { setOfficers(d); setLoading(false); })
      .catch(console.error)
  }, [token])

  useEffect(() => { load() }, [load])

  const handleAdd = async (e) => {
    e.preventDefault()
    const fd = new FormData(e.target)
    const body = Object.fromEntries(fd.entries())

    try {
      const res = await fetch(`${BASE_URL}/admin/officers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body)
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      showToast('Officer created successfully')
      setAddMode(false)
      load()
    } catch (err) {
      showToast(err.message, 'error')
    }
  }

  const handleToggleActive = async (id, isCurrentlyActive) => {
    try {
      const res = await fetch(`${BASE_URL}/admin/officers/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_active: !isCurrentlyActive })
      })
      if (!res.ok) throw new Error('Toggle failed')
      showToast(isCurrentlyActive ? 'Officer deactivated' : 'Officer activated')
      load()
    } catch (err) {
      showToast(err.message, 'error')
    }
  }

  const handleRowClick = async (off, e) => {
    // Ignore clicks on buttons/inputs
    if (e.target.tagName.toLowerCase() === 'button' || e.target.tagName.toLowerCase() === 'input') return

    if (expandedRow === off.id) {
      setExpandedRow(null)
      return
    }
    setExpandedRow(off.id)
    setExpandedData(null)
    if (statsCache.current.has(off.id)) {
      setExpandedData(statsCache.current.get(off.id))
    } else {
      try {
        const r = await fetch(`${BASE_URL}/admin/officers/${off.id}/stats`, { headers: { Authorization: `Bearer ${token}` }})
        const d = await r.json()
        statsCache.current.set(off.id, d)
        setExpandedData(d)
      } catch (err) { console.error(err) }
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <button onClick={() => setAddMode(!addMode)} style={{ ...styles.btnPrimary, background: addMode ? '#EF4444' : '#3B82F6' }}>
          {addMode ? 'Cancel' : '+ Add Officer'}
        </button>
      </div>

      {addMode && (
        <form onSubmit={handleAdd} style={styles.addForm}>
          <h3 style={{ margin: '0 0 16px', color: '#e8eaf0' }}>Create New Officer</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <input name="name" required placeholder="Full Name" style={styles.input} />
            <input name="email" type="email" required placeholder="Email Address" style={styles.input} />
            <input name="password" type="password" required placeholder="Password" style={styles.input} />
            <select name="zone" required style={styles.input}>
              <option value="">Select Zone...</option>
              {['Zone A','Zone B','Zone C','Zone D','All Zones'].map(z => <option key={z} value={z}>{z}</option>)}
            </select>
          </div>
          <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
            <button type="submit" style={styles.btnPrimary}>Create Officer</button>
          </div>
        </form>
      )}

      {loading ? <div style={styles.loading}>Loading officers...</div> : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr style={{ background: '#161a23' }}>
                <th style={styles.th}>Name</th>
                <th style={styles.th}>Email</th>
                <th style={styles.th}>Zone</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Assigned</th>
                <th style={styles.th}>Completed</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {officers.map(o => (
                <Fragment key={o.id}>
                  {editingId === o.id ? (
                    <InlineEditRow o={o} setEditingId={setEditingId} token={token} load={load} showToast={showToast} />
                  ) : (
                    <tr onClick={(e) => handleRowClick(o, e)} style={{ ...styles.tr, background: expandedRow === o.id ? '#1c2130' : 'transparent' }}>
                      <td style={{ ...styles.td, fontWeight: 600 }}>{o.name} {o.is_admin ? '(Admin)' : ''}</td>
                      <td style={styles.td}>{o.email}</td>
                      <td style={styles.td}>{o.zone || 'N/A'}</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.badge, background: o.is_active ? '#10B98122' : '#7a829922', color: o.is_active ? '#10B981' : '#7a8299' }}>
                          {o.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td style={styles.td}>{o.complaints_assigned}</td>
                      <td style={styles.td}>{o.complaints_completed}</td>
                      <td style={styles.td}>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={() => setEditingId(o.id)} style={styles.btnSmall}>Edit</button>
                          <button
                            disabled={o.id === currentOfficerId}
                            onClick={() => handleToggleActive(o.id, o.is_active)}
                            style={{ ...styles.btnSmall, color: o.id === currentOfficerId ? '#7a8299' : (o.is_active ? '#EF4444' : '#10B981') }}
                          >
                            {o.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                  {expandedRow === o.id && !editingId && (
                    <tr style={{ background: '#11151c' }}>
                      <td colSpan={7} style={{ padding: 20 }}>
                        {!expandedData ? <div style={{ color: '#7a8299', fontSize: 13 }}>Loading stats...</div> : (
                          <div style={{ display: 'flex', gap: 32 }}>
                            <div style={{ flex: 1 }}>
                              <h4 style={{ margin: '0 0 12px', color: '#f5a623' }}>Detailed Performance</h4>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
                                <div><strong>In Progress:</strong> {expandedData.in_progress}</div>
                                <div><strong>Pending:</strong> {expandedData.pending}</div>
                                <div><strong>Avg Resolution:</strong> {expandedData.avg_resolution_hours ? `${expandedData.avg_resolution_hours} hrs` : 'N/A'}</div>
                              </div>
                            </div>
                            <div style={{ flex: 2 }}>
                              <h4 style={{ margin: '0 0 12px', color: '#f5a623' }}>Recent Complaints</h4>
                              {expandedData.recent_complaints.length === 0 ? <p style={{fontSize:13, color:'#7a8299'}}>No recent complaints.</p> : (
                                <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                                  <tbody>
                                    {expandedData.recent_complaints.map(rc => (
                                      <tr key={rc.complaint_id} style={{ borderBottom: '1px solid #252b38' }}>
                                        <td style={{ padding: '6px 0', color: '#3B82F6' }}>{rc.complaint_id}</td>
                                        <td>{rc.damage_type.replace('_',' ')}</td>
                                        <td>{rc.status}</td>
                                        <td align="right" style={{color:'#7a8299'}}>{rc.created_at?.slice(0,10)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              )}
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function InlineEditRow({ o, setEditingId, token, load, showToast }) {
  const [form, setForm] = useState({ name: o.name, zone: o.zone || '' })

  const handleSave = async () => {
    try {
      const res = await fetch(`${BASE_URL}/admin/officers/${o.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form)
      })
      if (!res.ok) throw new Error('Update failed')
      showToast('Changes saved')
      setEditingId(null)
      load()
    } catch(e) {
      showToast(e.message, 'error')
    }
  }

  return (
    <tr style={{ background: '#1c2130' }}>
      <td style={styles.td}><input value={form.name} onChange={e => setForm({...form, name: e.target.value})} style={{...styles.input, padding: '4px 8px'}} autoFocus/></td>
      <td style={styles.td}><span style={{color: '#7a8299'}}>{o.email}</span></td>
      <td style={styles.td}>
        <select value={form.zone} onChange={e => setForm({...form, zone: e.target.value})} style={{...styles.input, padding: '4px 8px'}}>
          <option value="">N/A</option>
          {['Zone A','Zone B','Zone C','Zone D','All Zones'].map(z => <option key={z} value={z}>{z}</option>)}
        </select>
      </td>
      <td style={styles.td} colSpan={3} />
      <td style={styles.td}>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleSave} style={{...styles.btnSmall, background: '#10B981', color: '#000'}}>Save</button>
          <button onClick={() => setEditingId(null)} style={styles.btnSmall}>Cancel</button>
        </div>
      </td>
    </tr>
  )
}

InlineEditRow.propTypes = {
  o: PropTypes.object.isRequired,
  setEditingId: PropTypes.func.isRequired,
  token: PropTypes.string.isRequired,
  load: PropTypes.func.isRequired,
  showToast: PropTypes.func.isRequired,
}

OverviewTab.propTypes = {
  token: PropTypes.string.isRequired,
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  color: PropTypes.string,
}

OfficersTab.propTypes = {
  token: PropTypes.string.isRequired,
  currentOfficerId: PropTypes.number,
  showToast: PropTypes.func.isRequired,
}

const styles = {
  container: { minHeight: '100vh', background: '#0d0f14', color: '#e8eaf0', padding: '24px 32px', fontFamily: 'system-ui, sans-serif' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 },
  title: { fontSize: 24, fontWeight: 800, margin: 0 },
  subtitle: { color: '#7a8299', margin: '4px 0 0', fontSize: 14 },
  btnOutline: { background: 'transparent', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontSize: 14 },
  btnPrimary: { background: '#f5a623', color: '#000', border: 'none', borderRadius: 8, padding: '8px 16px', fontWeight: 600, cursor: 'pointer', fontSize: 14 },
  btnSmall: { background: '#252b38', color: '#e8eaf0', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12 },
  tabsWrap: { display: 'flex', gap: 32, borderBottom: '1px solid #252b38', marginBottom: 24 },
  tabBtn: { background: 'none', border: 'none', borderBottom: '3px solid transparent', padding: '12px 0', fontSize: 15, fontWeight: 600, cursor: 'pointer', outline: 'none' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 16, marginBottom: 16 },
  statCard: { background: '#161a23', borderRadius: 10, padding: '16px 20px', border: '1px solid #252b38' },
  chartWrap: { flex: '1 1 400px', background: '#161a23', borderRadius: 10, padding: 20, border: '1px solid #252b38' },
  chartTitle: { margin: '0 0 16px', fontSize: 15, color: '#e8eaf0' },
  tableWrap: { overflowX: 'auto', borderRadius: 12, border: '1px solid #252b38', background: '#161a23' },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: { padding: '12px 16px', textAlign: 'left', fontSize: 12, fontWeight: 700, color: '#7a8299', textTransform: 'uppercase', borderBottom: '1px solid #252b38' },
  td: { padding: '14px 16px', fontSize: 14, borderBottom: '1px solid #1c2130' },
  tr: { cursor: 'pointer', transition: 'background 0.15s' },
  badge: { padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700 },
  addForm: { background: '#161a23', padding: 20, borderRadius: 10, marginBottom: 20, border: '1px solid #252b38' },
  input: { background: '#0d0f14', color: '#e8eaf0', border: '1px solid #252b38', borderRadius: 8, padding: '10px 14px', fontSize: 14, width: '100%', boxSizing:'border-box' },
  loading: { padding: 40, textAlign: 'center', color: '#7a8299' },
  toastContainer: { position: 'fixed', bottom: 24, right: 24, display: 'flex', flexDirection: 'column', gap: 10, zIndex: 9999 },
  toast: { padding: '12px 20px', borderRadius: 8, color: '#fff', fontWeight: 600, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', animation: 'slideIn 0.3s ease' }
}
