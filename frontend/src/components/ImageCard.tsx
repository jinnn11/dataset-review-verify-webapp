import type { GeneratedImageRecord } from '../types'
import { imageUrl } from '../api'

interface ImageCardProps {
  image: GeneratedImageRecord
  isSelected: boolean
  isFocused: boolean
  onFocus: () => void
  onToggleSelect: () => void
}

export function ImageCard({ image, isSelected, isFocused, onFocus, onToggleSelect }: ImageCardProps) {
  return (
    <article
      className={`image-card ${isFocused ? 'focused' : ''} ${isSelected ? 'checked' : ''}`}
      onClick={() => {
        onFocus()
        onToggleSelect()
      }}
    >
      <button
        type="button"
        className={`select-radio ${isSelected ? 'checked' : ''}`}
        onClick={(event) => {
          event.stopPropagation()
          onToggleSelect()
        }}
        aria-label={isSelected ? `Deselect image ${image.id}` : `Select image ${image.id}`}
      />
      <div className="image-media">
        <img src={imageUrl(image.id)} alt={`Generated ${image.id}`} loading="lazy" />
      </div>
    </article>
  )
}
