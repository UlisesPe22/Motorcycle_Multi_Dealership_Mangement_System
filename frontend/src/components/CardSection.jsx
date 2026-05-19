export default function CardSection({ title, children }) {
  return (
    <div>
      <div className="card-section">{title}</div>
      {children}
    </div>
  )
}
