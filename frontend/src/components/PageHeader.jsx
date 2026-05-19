export default function PageHeader({ section, title }) {
  return (
    <div className="page-header">
      <div className="breadcrumb">
        Moto Dealer <span>/</span> {section}
      </div>
      <div className="page-title-bi">{title}</div>
      <hr className="page-rule" />
    </div>
  )
}
