const TAGS = { success: 'Correcto', error: 'Error', loading: 'Procesando' }

export default function StatusBox({ type, title, message, meta }) {
  return (
    <div className={`status-bi status-bi-${type}`}>
      <div className={`status-bi-tag status-bi-tag-${type}`}>{TAGS[type] ?? type}</div>
      <div className="status-bi-title">{title}</div>
      <div
        className="status-bi-msg"
        dangerouslySetInnerHTML={{ __html: message }}
      />
      {meta && <div className="status-bi-meta">{meta}</div>}
    </div>
  )
}
