export default function ClientDropdown({ filter, setFilter, selectedId, setSelectedId, options, placeholder }) {
  return (
    <div style={{ position: 'relative' }}>
      <input
        type="text"
        placeholder={placeholder || 'Buscar cliente...'}
        value={filter}
        onChange={e => { setFilter(e.target.value); if (selectedId) setSelectedId('') }}
        style={{ width: '100%', marginBottom: '0' }}
      />
      {filter.length > 0 && !selectedId && (
        <div style={{
          border: '1px solid #E2E8F0', borderRadius: '0 0 0.4rem 0.4rem',
          maxHeight: '180px', overflowY: 'auto', background: '#fff',
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        }}>
          {options.length === 0 ? (
            <div style={{ padding: '0.6rem 0.75rem', color: '#94A3B8', fontSize: '0.85rem' }}>Sin resultados</div>
          ) : (
            options.map(c => (
              <div
                key={c.client_id}
                style={{
                  padding: '0.5rem 0.75rem', cursor: 'pointer',
                  borderBottom: '1px solid #F1F5F9',
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#F8FAFC'}
                onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                onClick={() => {
                  setSelectedId(c.client_id)
                  setFilter(c.nombre_completo)
                }}
              >
                <strong style={{ fontSize: '0.88rem' }}>{c.nombre_completo}</strong>
                <span style={{ color: '#94A3B8', fontSize: '0.78rem', marginLeft: '0.5rem' }}>{c.rfc}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
