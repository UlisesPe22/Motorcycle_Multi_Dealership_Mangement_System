import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'

export default function Placeholders({ title = 'En construcción' }) {
  const navigate = useNavigate()
  return (
    <>
      <PageHeader section="Sistema" title={title} />
      <div className="col-center">
        <div className="placeholder-box">
          <div className="placeholder-title">En construcción</div>
          <div className="placeholder-msg">
            Esta sección estará disponible próximamente.<br />
            Estamos trabajando en ello.
          </div>
        </div>
        <div className="btn-row" style={{ justifyContent: 'center' }}>
          <button className="btn-primary" onClick={() => navigate('/')}>
            Volver al Panel Principal
          </button>
        </div>
      </div>
    </>
  )
}
