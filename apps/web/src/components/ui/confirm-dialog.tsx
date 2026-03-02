import { Modal } from './modal'
import { Button } from './button'

interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  description: string
  confirmLabel?: string
  dangerous?: boolean
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = 'Confirm',
  dangerous = false,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <p className="mb-6 font-mono text-sm text-foreground/70">{description}</p>
      <div className="flex items-center justify-end gap-3">
        <Button variant="secondary" size="sm" onClick={onClose}>
          Cancel
        </Button>
        {dangerous ? (
          <button
            onClick={onConfirm}
            className="inline-flex h-9 items-center justify-center border-2 border-red-500 bg-red-500/10 px-4 text-sm font-medium text-red-500 transition-all hover:bg-red-500/20"
          >
            {confirmLabel}
          </button>
        ) : (
          <Button variant="primary" size="sm" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        )}
      </div>
    </Modal>
  )
}
