import PropTypes from 'prop-types';

const cap = (str) => (str ? str.charAt(0).toUpperCase() + str.slice(1) : '');

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-US', { hour12: false });
}

export default function AdminFeedPanel({ events, isConnected, onClear }) {
  return (
    <div
      style={{
        width: '300px',
        flexShrink: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#161a23',
        borderLeft: '1px solid #252b38',
        color: '#e8eaf0',
        boxSizing: 'border-box',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px',
          borderBottom: '1px solid #252b38',
        }}
      >
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>Live Feed</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            title={isConnected ? 'Connected' : 'Disconnected'}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: isConnected ? '#22C55E' : '#EF4444',
            }}
          />
          <button
            onClick={onClear}
            style={{
              padding: '4px 8px',
              fontSize: '0.8rem',
              background: '#252b38',
              border: '1px solid #374151',
              borderRadius: '4px',
              cursor: 'pointer',
              color: '#e8eaf0',
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Event list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {events.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#6b7280', marginTop: '32px', fontSize: '0.875rem' }}>
            No live events yet
          </p>
        ) : (
          events.map((e, idx) => {
            const timeStr = formatTime(e.data?.created_at ?? e.data?.updated_at);

            let icon = '';
            let bg = '';
            let borderLeft = '';
            let line1 = null;
            let line2 = '';

            if (e.event === 'new_complaint') {
              icon = '🆕';
              bg = 'rgba(59,130,246,0.1)';
              borderLeft = '3px solid #3B82F6';
              const dt = cap(e.data?.damage_type ?? 'Unknown');
              const sev = cap(e.data?.severity ?? 'unknown');
              line1 = `${dt} — ${sev} severity`;
              line2 = `Priority: ${e.data?.priority_score ?? 0}/100`;
            } else if (e.event === 'officer_location') {
              icon = '📍';
              bg = 'rgba(16,185,129,0.1)';
              borderLeft = '3px solid #10B981';
              line1 = `Officer ${e.data?.name ?? 'Unknown'}`;
              line2 = `Zone: ${e.data?.zone ?? 'N/A'}  •  Location updated`;
            } else if (e.event === 'status_changed') {
              icon = '🔄';
              bg = 'rgba(245,158,11,0.1)';
              borderLeft = '3px solid #F59E0B';
              line1 = `Complaint ${e.data?.complaint_id ?? '—'}`;
              line2 = `→ ${cap(e.data?.new_status ?? '')}`;
            } else if (e.event === 'escalation') {
              icon = '🚨';
              bg = 'rgba(239,68,68,0.15)';
              borderLeft = '3px solid #EF4444';
              line1 = (
                <span style={{ fontWeight: 'bold', color: '#EF4444' }}>
                  ESCALATED — Level {e.data?.level ?? 1}
                </span>
              );
              line2 = `Complaint ${e.data?.complaint_id ?? '—'}  •  ${cap(e.data?.severity ?? '')}`;
            } else {
              return null;
            }

            return (
              <div
                key={idx}
                style={{
                  padding: '8px',
                  borderRadius: '4px',
                  marginBottom: '8px',
                  background: bg,
                  borderLeft,
                  fontSize: '0.8rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <span style={{ fontSize: '1.1rem', lineHeight: 1 }}>{icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: '500', color: '#e8eaf0', marginBottom: '2px' }}>{line1}</div>
                    <div style={{ color: '#9ca3af', marginBottom: '4px' }}>{line2}</div>
                    {timeStr && (
                      <div style={{ color: '#6b7280', fontSize: '0.7rem' }}>{timeStr}</div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

AdminFeedPanel.propTypes = {
  events: PropTypes.arrayOf(
    PropTypes.shape({
      event: PropTypes.string.isRequired,
      data: PropTypes.object.isRequired,
    })
  ).isRequired,
  isConnected: PropTypes.bool.isRequired,
  onClear: PropTypes.func.isRequired,
};
