import { BLUE, GREEN, GREY, BORDER } from '../constants'

// ─── Skeleton block (shimmer) ────────────────────────────────────────────────
function Skeleton({ width = '100%', height = 16, style = {} }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 4,
        background: 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.4s infinite',
        ...style,
      }}
    />
  )
}

// Shared header card used by VendorSales and Comisiones: 👤 + vendor name,
// a title on the right, and (optionally) the two vendor KPI chips.
export default function VendorHeaderCard({ summary, loading, title, showKpis = true }) {
  const isLoading = loading || !summary

  return (
    <div style={{
      background: '#fff',
      borderRadius: 8,
      boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
      padding: '20px 24px',
      marginBottom: 24,
    }}>
      {/* Self-contained shimmer keyframe so the skeleton animates anywhere */}
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <span style={{ fontSize: 22 }}>👤</span>
        <span style={{ fontSize: 18, fontWeight: 700, color: '#202124' }}>
          {isLoading ? <Skeleton width={120} height={20} /> : summary.vendor_name}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 18, fontWeight: 600, color: GREY }}>
          {title}
        </span>
      </div>

      {showKpis && (
        <>
          <div style={{ borderBottom: `1px solid ${BORDER}`, margin: '14px 0' }} />

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {/* KPI: Ventas Activas */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#E8F0FE',
              border: `1px solid #C5D8FB`,
              borderRadius: 20,
              padding: '6px 16px',
            }}>
              {isLoading ? (
                <Skeleton width={80} height={16} />
              ) : (
                <>
                  <span style={{ fontSize: 16, fontWeight: 700, color: BLUE }}>
                    {summary.sales_in_progress}
                  </span>
                  <span style={{ fontSize: 13, color: BLUE }}>Ventas Activas</span>
                </>
              )}
            </div>

            {/* KPI: Completadas este mes */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: '#E6F4EA',
              border: `1px solid #CEEAD6`,
              borderRadius: 20,
              padding: '6px 16px',
            }}>
              {isLoading ? (
                <Skeleton width={110} height={16} />
              ) : (
                <>
                  <span style={{ fontSize: 16, fontWeight: 700, color: GREEN }}>
                    {summary.completed_this_month}
                  </span>
                  <span style={{ fontSize: 13, color: GREEN }}>Completadas este mes</span>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
