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
      <p className="font-mono text-sm text-foreground/70 mb-6">{description}</p>
      <div className="flex items-center justify-end gap-3">
        <Button variant="secondary" size="sm" onClick={onClose}>
          Cancel
        </Button>
        {dangerous ? (
          <button
            onClick={onConfirm}
            className="inline-flex items-center justify-center font-medium transition-all h-9 px-4 text-sm border-2 border-red-500 text-red-500 bg-red-500/10 hover:bg-red-500/20"
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
