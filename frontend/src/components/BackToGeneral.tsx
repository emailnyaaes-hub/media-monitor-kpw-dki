import { useNavigate } from 'react-router-dom'
import { useFilters } from '../filters'

export default function BackToGeneral() {
  const filters = useFilters()
  const navigate = useNavigate()
  if (!filters.narrowed) return null
  return (
    <button
      className="mb-2 h-8 w-fit rounded-md bg-navy-900 px-3 text-sm text-white"
      onClick={() => {
        const saved = filters.backToGeneral()
        if (saved?.returnTo) navigate(saved.returnTo)
      }}
    >
      Kembali ke tampilan umum
    </button>
  )
}
