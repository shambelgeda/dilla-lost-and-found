import { useCallback, useEffect, useEffectEvent, useMemo, useState } from 'react'
import './App.css'

const API_BASE = '/api/v1'
const DEFAULT_LOGIN = {
  university_id_or_email: '',
  password: '',
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('dilla_token') || '')
  const [user, setUser] = useState(JSON.parse(localStorage.getItem('dilla_user') || 'null'))
  const [loginForm, setLoginForm] = useState(DEFAULT_LOGIN)
  const [loginError, setLoginError] = useState('')
  const [authMode, setAuthMode] = useState('login')
  const [registrationForm, setRegistrationForm] = useState({
    university_id: '',
    full_name: '',
    email: '',
    phone: '',
    password: '',
  })
  const [health, setHealth] = useState(null)
  const [categories, setCategories] = useState([])
  const [locations, setLocations] = useState([])
  const [items, setItems] = useState([])
  const [claims, setClaims] = useState([])
  const [matches, setMatches] = useState([])
  const [notifications, setNotifications] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [analyticsTrends, setAnalyticsTrends] = useState([])
  const [accounts, setAccounts] = useState([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [view, setView] = useState('overview')
  const [browseSearch, setBrowseSearch] = useState('')
  const [actionFeedback, setActionFeedback] = useState('')
  const [claimTarget, setClaimTarget] = useState(null)
  const [claimProof, setClaimProof] = useState('')
  const [claimLostItemId, setClaimLostItemId] = useState('')
  const [claimReviewId, setClaimReviewId] = useState(null)
  const [officerNotes, setOfficerNotes] = useState('')
  const [handoverCode, setHandoverCode] = useState('')
  const [handoverNotes, setHandoverNotes] = useState('')
  const [reportImage, setReportImage] = useState(null)
  const [editingItemId, setEditingItemId] = useState(null)
  const [confirmDeleteItemId, setConfirmDeleteItemId] = useState(null)
  const [reportForm, setReportForm] = useState(() => ({
    report_type: 'LOST',
    title: '',
    description: '',
    category_id: '',
    location_id: '',
    incident_date: new Date().toISOString().slice(0, 16),
    confidential_identifiers: '',
  }))

  const activeLocationName = useMemo(() => {
    const selectedLocationId = reportForm.location_id || locations[0]?.id
    return locations.find((loc) => loc.id === selectedLocationId)?.block_or_facility || 'Select a location'
  }, [locations, reportForm.location_id])

  const authenticated = Boolean(token && user)
  const hasStaffAccess = ['ADMIN', 'SECURITY_OFFICER'].includes(user?.role)
  const isAdmin = user?.role === 'ADMIN'

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })

    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json') ? await response.json() : await response.text()

    if (!response.ok) {
      const message = typeof payload === 'string' ? payload : payload.detail || 'Request failed'
      throw new Error(message)
    }

    return payload
  }

  const loadDashboardData = useCallback(async () => {
    try {
      const authHeaders = { Authorization: `Bearer ${token}` }
      const [healthResponse, categoriesResponse, locationsResponse, itemsResponse, currentUser] = await Promise.all([
        fetchJson(`${API_BASE}/health`),
        fetchJson(`${API_BASE}/categories`),
        fetchJson(`${API_BASE}/locations`),
        fetchJson(`${API_BASE}/items`, { headers: authHeaders }),
        fetchJson(`${API_BASE}/auth/me`, { headers: authHeaders }),
      ])

      setUser(currentUser)
      localStorage.setItem('dilla_user', JSON.stringify(currentUser))
      setHealth(healthResponse)
      setCategories(categoriesResponse)
      setLocations(locationsResponse)
      setItems(itemsResponse)

      const [claimsResponse, matchesResponse, notificationsResponse, analyticsResponse, trendsResponse, accountsResponse] = await Promise.all([
        fetchJson(`${API_BASE}/claims`, { headers: authHeaders }),
        fetchJson(`${API_BASE}/matches/${hasStaffAccess ? 'review-queue' : 'my-matches'}`, { headers: authHeaders }),
        fetchJson(`${API_BASE}/notifications`, { headers: authHeaders }),
        hasStaffAccess ? fetchJson(`${API_BASE}/analytics/overview`, { headers: authHeaders }) : Promise.resolve(null),
        hasStaffAccess ? fetchJson(`${API_BASE}/analytics/trends`, { headers: authHeaders }) : Promise.resolve([]),
        isAdmin ? fetchJson(`${API_BASE}/auth/users`, { headers: authHeaders }) : Promise.resolve([]),
      ])

      setClaims(claimsResponse)
      setMatches(matchesResponse)
      setNotifications(notificationsResponse)
      setAnalytics(analyticsResponse)
      setAnalyticsTrends(trendsResponse)
      setAccounts(accountsResponse)
    } catch (err) {
      console.error('Dashboard load failed', err)
    }
  }, [hasStaffAccess, isAdmin, token])

  const syncDashboardData = useEffectEvent(() => {
    loadDashboardData()
  })

  useEffect(() => {
    if (authenticated) syncDashboardData()
  }, [authenticated])

  const handleAuthSubmit = async (event) => {
    event.preventDefault()
    setLoginError('')

    try {
      const isRegistration = authMode === 'register'
      const response = await fetchJson(`${API_BASE}/auth/${isRegistration ? 'register' : 'login'}`, {
        method: 'POST',
        body: JSON.stringify(isRegistration ? registrationForm : loginForm),
      })

      localStorage.setItem('dilla_token', response.access_token)
      localStorage.setItem('dilla_user', JSON.stringify(response.user))
      setToken(response.access_token)
      setUser(response.user)
      setView('overview')
    } catch (err) {
      setLoginError(err.message)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('dilla_token')
    localStorage.removeItem('dilla_user')
    setToken('')
    setUser(null)
    setView('overview')
  }

  const handleClaimSubmit = async (event) => {
    event.preventDefault()
    setActionFeedback('')

    try {
      await fetchJson(`${API_BASE}/claims`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          found_item_id: claimTarget,
          lost_item_id: claimLostItemId || null,
          proof_description: claimProof,
        }),
      })
      setClaimTarget(null)
      setClaimProof('')
      setClaimLostItemId('')
      setActionFeedback({ type: 'success', message: 'Claim submitted. You can track its status under Claims.' })
      await loadDashboardData()
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleClaimReview = async (claimId, status) => {
    setActionFeedback('')
    try {
      await fetchJson(`${API_BASE}/claims/${claimId}/verify`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status, officer_notes: officerNotes || null }),
      })
      setClaimReviewId(null)
      setOfficerNotes('')
      setActionFeedback({ type: 'success', message: `Claim ${status.toLowerCase()}.` })
      await loadDashboardData()
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleHandover = async (event, claimId) => {
    event.preventDefault()
    setActionFeedback('')
    try {
      await fetchJson(`${API_BASE}/claims/${claimId}/handover`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ verification_code: handoverCode, handover_notes: handoverNotes || null }),
      })
      setHandoverCode('')
      setHandoverNotes('')
      setActionFeedback({ type: 'success', message: 'Physical handover recorded.' })
      await loadDashboardData()
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleMatchStatus = async (matchId, status) => {
    setActionFeedback('')
    try {
      await fetchJson(`${API_BASE}/matches/${matchId}/status`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      })
      setActionFeedback({ type: 'success', message: `Match ${status.toLowerCase()}.` })
      await loadDashboardData()
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleTriggerMatching = async (itemId) => {
    setActionFeedback('')
    try {
      await fetchJson(`${API_BASE}/matches/trigger/${itemId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      setActionFeedback({ type: 'success', message: 'AI matching completed. Review the updated matches.' })
      await loadDashboardData()
      setView('matches')
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleMarkRead = async (notificationId) => {
    try {
      await fetchJson(`${API_BASE}/notifications/${notificationId}/read`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      setNotifications((current) => current.map((notification) => (
        notification.id === notificationId ? { ...notification, is_read: true } : notification
      )))
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await fetchJson(`${API_BASE}/notifications/read-all`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      })
      setNotifications((current) => current.map((notification) => ({ ...notification, is_read: true })))
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleUserRoleChange = async (userId, role) => {
    try {
      const updatedUser = await fetchJson(`${API_BASE}/auth/users/${userId}/role`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ role }),
      })
      setAccounts((current) => current.map((account) => account.id === updatedUser.id ? updatedUser : account))
      setActionFeedback({ type: 'success', message: `Role updated for ${updatedUser.full_name}.` })
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleEditItem = (item) => {
    setEditingItemId(item.id)
    setReportForm({
      report_type: item.report_type,
      title: item.title,
      description: item.description,
      category_id: item.category_id,
      location_id: item.location_id,
      incident_date: new Date(item.incident_date).toISOString().slice(0, 16),
      confidential_identifiers: item.confidential_identifiers || '',
    })
    setView('report')
  }

  const handleDeleteItem = async (itemId) => {
    try {
      await fetchJson(`${API_BASE}/items/${itemId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      setItems((current) => current.filter((item) => item.id !== itemId))
      setConfirmDeleteItemId(null)
      setActionFeedback({ type: 'success', message: 'Report deleted.' })
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    }
  }

  const handleReportSubmit = async (event) => {
    event.preventDefault()
    setIsSubmitting(true)

    try {
      if (editingItemId) {
        const payload = await fetchJson(`${API_BASE}/items/${editingItemId}`, {
          method: 'PATCH',
          headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            title: reportForm.title,
            description: reportForm.description,
            category_id: reportForm.category_id || categories[0]?.id,
            location_id: reportForm.location_id || locations[0]?.id,
            confidential_identifiers: reportForm.confidential_identifiers || null,
          }),
        })
        setItems((current) => current.map((item) => item.id === payload.id ? payload : item))
        setEditingItemId(null)
        setActionFeedback({ type: 'success', message: 'Report updated.' })
        setView('my-reports')
        return
      }

      const formData = new FormData()
      formData.append('report_type', reportForm.report_type)
      formData.append('title', reportForm.title)
      formData.append('description', reportForm.description)
      formData.append('category_id', reportForm.category_id || categories[0]?.id || '')
      formData.append('location_id', reportForm.location_id || locations[0]?.id || '')
      formData.append('incident_date', new Date(reportForm.incident_date).toISOString())
      formData.append('confidential_identifiers', reportForm.confidential_identifiers || '')
      if (reportImage) formData.append('image', reportImage)

      const response = await fetch(`${API_BASE}/items`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload.detail || 'Item report failed')
      }

      setItems((current) => [payload, ...current])
  setReportImage(null)
      setReportForm({
        report_type: 'LOST',
        title: '',
        description: '',
        category_id: categories[0]?.id || '',
        location_id: locations[0]?.id || '',
        incident_date: new Date().toISOString().slice(0, 16),
        confidential_identifiers: '',
      })
      setView('overview')
    } catch (err) {
      setActionFeedback({ type: 'error', message: err.message })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!authenticated) {
    return (
      <div className="auth-shell">
        <div className="auth-card">
          <p className="kicker">Dilla University</p>
          <h1>{authMode === 'register' ? 'Create your account' : 'Lost & Found Portal'}</h1>
          <p className="subtitle">
            {authMode === 'register'
              ? 'Register a student account to report and track lost or found items.'
              : 'Sign in to report items, review matches, and manage claims.'}
          </p>
          <form onSubmit={handleAuthSubmit} className="auth-form">
            {authMode === 'register' ? (
              <>
                <label>
                  University ID
                  <input
                    value={registrationForm.university_id}
                    onChange={(event) => setRegistrationForm({ ...registrationForm, university_id: event.target.value })}
                    required
                  />
                </label>
                <label>
                  Full name
                  <input
                    value={registrationForm.full_name}
                    onChange={(event) => setRegistrationForm({ ...registrationForm, full_name: event.target.value })}
                    required
                  />
                </label>
                <label>
                  University email
                  <input
                    type="email"
                    value={registrationForm.email}
                    onChange={(event) => setRegistrationForm({ ...registrationForm, email: event.target.value })}
                    required
                  />
                </label>
                <label>
                  Phone (optional)
                  <input
                    type="tel"
                    value={registrationForm.phone}
                    onChange={(event) => setRegistrationForm({ ...registrationForm, phone: event.target.value })}
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    minLength="8"
                    value={registrationForm.password}
                    onChange={(event) => setRegistrationForm({ ...registrationForm, password: event.target.value })}
                    required
                  />
                </label>
              </>
            ) : (
              <>
                <label>
                  University ID or Email
                  <input
                    value={loginForm.university_id_or_email}
                    onChange={(event) => setLoginForm({ ...loginForm, university_id_or_email: event.target.value })}
                    required
                  />
                </label>
                <label>
                  Password
                  <input
                    type="password"
                    value={loginForm.password}
                    onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })}
                    required
                  />
                </label>
              </>
            )}
            {loginError && <p className="error-text">{loginError}</p>}
            <button className="primary-btn" type="submit">
              {authMode === 'register' ? 'Create account' : 'Sign in'}
            </button>
          </form>
          <div className="auth-switch">
            {authMode === 'register' ? 'Already registered?' : 'New to the portal?'}
            <button
              type="button"
              className="text-btn"
              onClick={() => {
                setLoginError('')
                setAuthMode(authMode === 'register' ? 'login' : 'register')
              }}
            >
              {authMode === 'register' ? 'Sign in' : 'Create an account'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="kicker">Dilla University</p>
          <h1>Lost & Found Portal</h1>
        </div>
        <div className="topbar-actions">
          <span className="user-badge">{user?.full_name} · {user?.role?.replaceAll('_', ' ')}</span>
          <button type="button" className={view === 'overview' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('overview')}>
            Overview
          </button>
          <button type="button" className={view === 'report' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('report')}>
            Report item
          </button>
          <button type="button" className={view === 'my-reports' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('my-reports')}>
            My reports ({items.filter((item) => item.user_id === user?.id).length})
          </button>
          <button type="button" className={view === 'browse' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('browse')}>
            Browse found
          </button>
          <button type="button" className={view === 'matches' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('matches')}>
            Matches ({matches.length})
          </button>
          <button type="button" className={view === 'claims' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('claims')}>
            Claims ({claims.filter((claim) => ['SUBMITTED', 'UNDER_REVIEW'].includes(claim.status)).length})
          </button>
          <button type="button" className={view === 'notifications' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('notifications')}>
            Alerts ({notifications.filter((notification) => !notification.is_read).length})
          </button>
          {hasStaffAccess && (
            <button type="button" className={view === 'analytics' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('analytics')}>
              Analytics
            </button>
          )}
          {isAdmin && (
            <button type="button" className={view === 'accounts' ? 'primary-btn' : 'secondary-btn'} onClick={() => setView('accounts')}>
              Accounts ({accounts.length})
            </button>
          )}
          <button type="button" className="primary-btn" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      {actionFeedback && (
        <div className={`action-feedback ${actionFeedback.type}`} role="status">
          {actionFeedback.message}
        </div>
      )}

      <main className="dashboard-grid">
        {view === 'overview' && (
          <>
        <section className="panel highlight-panel">
          <p className="panel-label">System status</p>
          {!health && <p>Connecting to backend…</p>}
          {health && (
            <>
              <h2>{health.status}</h2>
              <p className="service-name">{health.service}</p>
              <div className="metric-row">
                <div>
                  <span>Image</span>
                  <strong>{health.weights.image}</strong>
                </div>
                <div>
                  <span>Text</span>
                  <strong>{health.weights.text}</strong>
                </div>
                <div>
                  <span>Metadata</span>
                  <strong>{health.weights.metadata}</strong>
                </div>
              </div>
            </>
          )}
        </section>

        <section className="panel">
          <p className="panel-label">Quick actions</p>
          <ul className="action-list">
            <li>Lost item report</li>
            <li>Found item report</li>
            <li>AI match review</li>
            <li>Claim verification</li>
          </ul>
        </section>

        <section className="panel wide-panel">
          <p className="panel-label">Live overview</p>
          <div className="stats-grid">
            <div>
              <span>Open cases</span>
              <strong>{items.filter((item) => item.status === 'OPEN').length || 0}</strong>
            </div>
            <div>
              <span>Pending claims</span>
              <strong>{claims.filter((claim) => ['SUBMITTED', 'UNDER_REVIEW'].includes(claim.status)).length}</strong>
            </div>
            <div>
              <span>{hasStaffAccess ? 'Matches in queue' : 'Your matches'}</span>
              <strong>{hasStaffAccess ? analytics?.total_matches_found ?? matches.length : matches.length}</strong>
            </div>
            <div>
              <span>Resolved</span>
              <strong>{items.filter((item) => item.status === 'RESOLVED').length || 0}</strong>
            </div>
          </div>
        </section>
          </>
        )}

        {view === 'report' && (
          <section className="panel wide-panel form-panel">
            <p className="panel-label">{editingItemId ? 'Edit report' : 'New report'}</p>
            <form className="report-form" onSubmit={handleReportSubmit}>
              <div className="field-row">
                <label>
                  Report type
                  <select
                    value={reportForm.report_type}
                    onChange={(event) => setReportForm({ ...reportForm, report_type: event.target.value })}
                    disabled={Boolean(editingItemId)}
                  >
                    <option value="LOST">Lost</option>
                    <option value="FOUND">Found</option>
                  </select>
                </label>
                <label>
                  Title
                  <input
                    value={reportForm.title}
                    onChange={(event) => setReportForm({ ...reportForm, title: event.target.value })}
                    placeholder="e.g. Blue Samsung Galaxy A53"
                    required
                  />
                </label>
              </div>

              <label>
                Description
                <textarea
                  value={reportForm.description}
                  onChange={(event) => setReportForm({ ...reportForm, description: event.target.value })}
                  rows="4"
                  required
                />
              </label>

              <div className="field-row">
                <label>
                  Category
                  <select
                    value={reportForm.category_id || categories[0]?.id || ''}
                    onChange={(event) => setReportForm({ ...reportForm, category_id: event.target.value })}
                    required
                  >
                    {categories.map((category) => (
                      <option key={category.id} value={category.id}>{category.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Location
                  <select
                    value={reportForm.location_id || locations[0]?.id || ''}
                    onChange={(event) => setReportForm({ ...reportForm, location_id: event.target.value })}
                    required
                  >
                    {locations.map((location) => (
                      <option key={location.id} value={location.id}>
                        {location.campus_name} · {location.block_or_facility}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="field-row">
                <label>
                  Incident date
                  <input
                    type="datetime-local"
                    value={reportForm.incident_date}
                    onChange={(event) => setReportForm({ ...reportForm, incident_date: event.target.value })}
                    disabled={Boolean(editingItemId)}
                    required
                  />
                </label>
                <label>
                  Confidential identifiers
                  <input
                    value={reportForm.confidential_identifiers}
                    onChange={(event) => setReportForm({ ...reportForm, confidential_identifiers: event.target.value })}
                    placeholder="Serial number / custom ID for verification"
                  />
                </label>
              </div>

              {!editingItemId && (
                <label>
                  Item photo (optional)
                  <input type="file" accept="image/*" onChange={(event) => setReportImage(event.target.files?.[0] || null)} />
                  {reportImage && <span className="muted-text">Selected: {reportImage.name}</span>}
                </label>
              )}

              <div className="location-note">
                Selected location: <strong>{activeLocationName}</strong>
              </div>

              <button type="submit" className="primary-btn" disabled={isSubmitting}>
                {isSubmitting ? 'Saving…' : editingItemId ? 'Save changes' : 'Submit report'}
              </button>
              {editingItemId && (
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => {
                    setEditingItemId(null)
                    setReportForm({ report_type: 'LOST', title: '', description: '', category_id: '', location_id: '', incident_date: new Date().toISOString().slice(0, 16), confidential_identifiers: '' })
                    setView('my-reports')
                  }}
                >
                  Cancel editing
                </button>
              )}
            </form>
          </section>
        )}

        {view === 'my-reports' && (
          <section className="panel wide-panel">
            <p className="panel-label">Reports submitted by you</p>
            <div className="items-grid">
              {items.filter((item) => item.user_id === user?.id).length === 0 && <p className="empty-state">You have not submitted any reports.</p>}
              {items.filter((item) => item.user_id === user?.id).map((item) => (
                <article key={item.id} className="item-card">
                  <div className="item-header">
                    <span className={`badge ${item.report_type.toLowerCase()}`}>{item.report_type}</span>
                    <span className="status-badge">{item.status}</span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <div className="meta-row">
                    <span>{categories.find((category) => category.id === item.category_id)?.name || 'Unknown category'}</span>
                    <span>{locations.find((location) => location.id === item.location_id)?.block_or_facility || 'Unknown location'}</span>
                  </div>
                  <div className="inline-actions">
                    <button className="secondary-btn" type="button" onClick={() => handleEditItem(item)}>Edit report</button>
                    {confirmDeleteItemId === item.id ? (
                      <>
                        <span className="muted-text">Delete this report?</span>
                        <button className="danger-btn" type="button" onClick={() => handleDeleteItem(item.id)}>Confirm delete</button>
                        <button className="secondary-btn" type="button" onClick={() => setConfirmDeleteItemId(null)}>Keep report</button>
                      </>
                    ) : (
                      <button className="danger-btn" type="button" onClick={() => setConfirmDeleteItemId(item.id)}>Delete report</button>
                    )}
                    <button className="text-btn" type="button" onClick={() => handleTriggerMatching(item.id)}>Run AI matching</button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'overview' && (
          <section className="panel wide-panel">
            <p className="panel-label">Recent reports</p>
            <div className="items-grid">
              {items.length === 0 && <p>No items yet.</p>}
              {items.slice(0, 8).map((item) => (
                <article key={item.id} className="item-card">
                  <div className="item-header">
                    <span className={`badge ${item.report_type.toLowerCase()}`}>{item.report_type}</span>
                    <span className="status-badge">{item.status}</span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <div className="meta-row">
                    <span>{categories.find((cat) => cat.id === item.category_id)?.name || 'Unknown category'}</span>
                    <span>{locations.find((loc) => loc.id === item.location_id)?.block_or_facility || 'Unknown location'}</span>
                    {(item.user_id === user?.id || hasStaffAccess) && (
                      <button className="text-btn align-start" type="button" onClick={() => handleTriggerMatching(item.id)}>
                        Run AI matching
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'browse' && (
          <section className="panel wide-panel">
            <div className="panel-heading-row">
              <div>
                <p className="panel-label">Available found items</p>
                <h2>Browse and claim</h2>
              </div>
              <input
                className="filter-input"
                aria-label="Search found items"
                placeholder="Search by title or description"
                value={browseSearch}
                onChange={(event) => setBrowseSearch(event.target.value)}
              />
            </div>
            <div className="items-grid">
              {items
                .filter((item) => item.report_type === 'FOUND' && item.status !== 'RESOLVED')
                .filter((item) => `${item.title} ${item.description}`.toLowerCase().includes(browseSearch.toLowerCase()))
                .map((item) => (
                  <article key={item.id} className="item-card">
                    <div className="item-header">
                      <span className="badge found">FOUND</span>
                      <span className="status-badge">{item.status}</span>
                    </div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                    <div className="meta-row">
                      <span>{categories.find((cat) => cat.id === item.category_id)?.name || 'Unknown category'}</span>
                      <span>{locations.find((loc) => loc.id === item.location_id)?.block_or_facility || 'Unknown location'}</span>
                      <span>{new Date(item.incident_date).toLocaleDateString()}</span>
                    </div>
                    {claimTarget === item.id ? (
                      <form className="report-form claim-form" onSubmit={handleClaimSubmit}>
                        <label>
                          Link to your lost report (optional)
                          <select value={claimLostItemId} onChange={(event) => setClaimLostItemId(event.target.value)}>
                            <option value="">No linked report</option>
                            {items.filter((lostItem) => lostItem.user_id === user?.id && lostItem.report_type === 'LOST').map((lostItem) => (
                              <option key={lostItem.id} value={lostItem.id}>{lostItem.title}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Proof of ownership
                          <textarea value={claimProof} onChange={(event) => setClaimProof(event.target.value)} rows="3" required />
                        </label>
                        <div className="inline-actions">
                          <button type="submit" className="primary-btn">Submit claim</button>
                          <button type="button" className="secondary-btn" onClick={() => setClaimTarget(null)}>Cancel</button>
                        </div>
                      </form>
                    ) : (
                      <button
                        type="button"
                        className="secondary-btn claim-action"
                        disabled={item.user_id === user?.id || claims.some((claim) => claim.found_item_id === item.id && ['SUBMITTED', 'UNDER_REVIEW'].includes(claim.status))}
                        onClick={() => setClaimTarget(item.id)}
                      >
                        {item.user_id === user?.id ? 'Your found report' : claims.some((claim) => claim.found_item_id === item.id && ['SUBMITTED', 'UNDER_REVIEW'].includes(claim.status)) ? 'Claim pending' : 'Claim this item'}
                      </button>
                    )}
                  </article>
                ))}
            </div>
          </section>
        )}

        {view === 'matches' && (
          <section className="panel wide-panel">
            <p className="panel-label">{hasStaffAccess ? 'Officer review queue' : 'Matches for your reports'}</p>
            <div className="workflow-list">
              {matches.length === 0 && <p className="empty-state">No active matches to review.</p>}
              {matches.map((match) => (
                <article key={match.id} className="workflow-card">
                  <div className="item-header">
                    <span className="status-badge">{match.status}</span>
                    <strong className="score">{Math.round(match.final_score * 100)}% match</strong>
                  </div>
                  <div className="match-pair">
                    <div><span>Lost report</span><strong>{match.lost_item?.title || 'Unavailable'}</strong></div>
                    <div><span>Found report</span><strong>{match.found_item?.title || 'Unavailable'}</strong></div>
                  </div>
                  <p className="score-detail">
                    Text {Math.round(match.text_score * 100)}% · Image {Math.round(match.image_score * 100)}% · Details {Math.round(match.meta_score * 100)}%
                  </p>
                  {['SUGGESTED', 'OFFICER_REVIEW'].includes(match.status) && (
                    <div className="inline-actions">
                      <button className="primary-btn" type="button" onClick={() => handleMatchStatus(match.id, 'CONFIRMED')}>Confirm match</button>
                      <button className="secondary-btn" type="button" onClick={() => handleMatchStatus(match.id, 'DISMISSED')}>Dismiss</button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'claims' && (
          <section className="panel wide-panel">
            <p className="panel-label">{hasStaffAccess ? 'Claim verification queue' : 'Your claims'}</p>
            <div className="workflow-list">
              {claims.length === 0 && <p className="empty-state">No claims yet.</p>}
              {claims.map((claim) => (
                <article key={claim.id} className="workflow-card">
                  <div className="item-header">
                    <span className="status-badge">{claim.status}</span>
                    <span className="muted-text">{new Date(claim.created_at).toLocaleString()}</span>
                  </div>
                  <h3>{claim.found_item?.title || 'Found item'}</h3>
                  {hasStaffAccess && <p className="muted-text">Claimant: {claim.claimant?.full_name} · {claim.claimant?.university_id}</p>}
                  <p>{claim.proof_description}</p>
                  {claim.officer_notes && <p className="officer-notes">Officer note: {claim.officer_notes}</p>}
                  {claim.handover_code && claim.status === 'APPROVED' && !hasStaffAccess && (
                    <p className="pickup-code">Pickup verification code: <strong>{claim.handover_code}</strong></p>
                  )}
                  {hasStaffAccess && ['SUBMITTED', 'UNDER_REVIEW'].includes(claim.status) && (
                    claimReviewId === claim.id ? (
                      <div className="review-actions">
                        <label>
                          Officer notes
                          <textarea value={officerNotes} onChange={(event) => setOfficerNotes(event.target.value)} rows="2" />
                        </label>
                        <div className="inline-actions">
                          {claim.status === 'SUBMITTED' && <button className="secondary-btn" type="button" onClick={() => handleClaimReview(claim.id, 'UNDER_REVIEW')}>Start review</button>}
                          <button className="primary-btn" type="button" onClick={() => handleClaimReview(claim.id, 'APPROVED')}>Approve</button>
                          <button className="danger-btn" type="button" onClick={() => handleClaimReview(claim.id, 'REJECTED')}>Reject</button>
                          <button className="secondary-btn" type="button" onClick={() => setClaimReviewId(null)}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <button className="secondary-btn" type="button" onClick={() => setClaimReviewId(claim.id)}>Review claim</button>
                    )
                  )}
                  {hasStaffAccess && claim.status === 'APPROVED' && (
                    <form className="report-form handover-form" onSubmit={(event) => handleHandover(event, claim.id)}>
                      <label>
                        Student pickup code
                        <input value={handoverCode} onChange={(event) => setHandoverCode(event.target.value)} required />
                      </label>
                      <label>
                        Handover notes (optional)
                        <input value={handoverNotes} onChange={(event) => setHandoverNotes(event.target.value)} />
                      </label>
                      <button type="submit" className="primary-btn">Confirm physical handover</button>
                    </form>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'notifications' && (
          <section className="panel wide-panel">
            <div className="panel-heading-row">
              <p className="panel-label">Notifications</p>
              {notifications.some((notification) => !notification.is_read) && (
                <button type="button" className="secondary-btn" onClick={handleMarkAllRead}>Mark all read</button>
              )}
            </div>
            <div className="workflow-list">
              {notifications.length === 0 && <p className="empty-state">No notifications yet.</p>}
              {notifications.map((notification) => (
                <article key={notification.id} className={`notification-row ${notification.is_read ? 'read' : 'unread'}`}>
                  <div>
                    <div className="item-header">
                      <strong>{notification.title}</strong>
                      <span className="muted-text">{new Date(notification.created_at).toLocaleString()}</span>
                    </div>
                    <p>{notification.message}</p>
                  </div>
                  {!notification.is_read && <button type="button" className="text-btn" onClick={() => handleMarkRead(notification.id)}>Mark read</button>}
                </article>
              ))}
            </div>
          </section>
        )}

        {view === 'accounts' && isAdmin && (
          <section className="panel wide-panel">
            <p className="panel-label">Account access</p>
            <div className="workflow-list">
              {accounts.map((account) => (
                <article key={account.id} className="workflow-card account-row">
                  <div className="account-info">
                    <h3>{account.full_name}</h3>
                    <p>{account.university_id} · {account.email}</p>
                    <span className="muted-text">{account.is_active ? 'Active account' : 'Inactive account'}</span>
                  </div>
                  <label className="account-role">
                    Role
                    <select
                      value={account.role}
                      disabled={account.id === user?.id}
                      onChange={(event) => handleUserRoleChange(account.id, event.target.value)}
                    >
                      <option value="STUDENT">Student</option>
                      <option value="STAFF">Staff</option>
                      <option value="SECURITY_OFFICER">Security officer</option>
                      <option value="ADMIN">Administrator</option>
                    </select>
                  </label>
                </article>
              ))}
              {accounts.length === 0 && <p className="empty-state">No accounts found.</p>}
            </div>
          </section>
        )}

        {view === 'analytics' && hasStaffAccess && analytics && (
          <>
            <section className="panel wide-panel">
              <p className="panel-label">Operational analytics</p>
              <div className="stats-grid">
                <div><span>Lost reports</span><strong>{analytics.total_lost_reported}</strong></div>
                <div><span>Found reports</span><strong>{analytics.total_found_reported}</strong></div>
                <div><span>Matches</span><strong>{analytics.total_matches_found}</strong></div>
                <div><span>Recovered</span><strong>{analytics.recovery_rate_percentage}%</strong></div>
              </div>
            </section>
            <section className="panel">
              <p className="panel-label">Campus hotspots</p>
              <div className="compact-list">
                {analytics.hotspots.map((spot) => (
                  <div key={`${spot.campus_name}-${spot.block_or_facility}`}><strong>{spot.block_or_facility}</strong><span>{spot.campus_name} · {spot.lost_count} lost / {spot.found_count} found</span></div>
                ))}
              </div>
            </section>
            <section className="panel">
              <p className="panel-label">Monthly activity</p>
              <div className="compact-list">
                {analyticsTrends.map((trend) => (
                  <div key={trend.month}><strong>{trend.month}</strong><span>{trend.lost_reports} lost · {trend.found_reports} found · {trend.approved_claims} recovered</span></div>
                ))}
              </div>
            </section>
          </>
        )}

      </main>
    </div>
  )
}

export default App
