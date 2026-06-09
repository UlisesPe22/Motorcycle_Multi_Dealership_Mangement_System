export default function Toast({ toast, onClose }) {
  if (!toast) return null
  const bg = toast.type === 'success' ? '#DCFCE7' : '#FEE2E2'
  const fg = toast.type === 'success' ? '#15803D' : '#DC2626'
  return (
    <div style={{
      position: 'fixed', top: '1.5rem', right: '1.5rem', zIndex: 1000,
      background: bg, color: fg, border: `1px solid ${fg}`,
      borderRadius: '0.5rem', padding: '0.75rem 1.25rem',
      fontWeight: 600, fontSize: '0.9rem', boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
      maxWidth: '360px',
    }}>
      {toast.message}
      <button
        onClick={onClose}
        style={{ marginLeft: '1rem', background: 'none', border: 'none', cursor: 'pointer', color: fg, fontWeight: 700 }}
      >
        ×
      </button>
    </div>
  )
}
