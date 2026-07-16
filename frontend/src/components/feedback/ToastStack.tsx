import { useEffect, useState } from 'react'
import { Alert, Snackbar } from '@mui/material'
import { useAppDispatch, useAppSelector } from '@/app/hooks'
import { dismissed, selectNotificationQueue, type AppNotification } from '@/notifications/notificationsSlice'

const AUTO_HIDE_MS = 5000

/** Renders one toast at a time from the notifications queue (MUI's
 * "consecutive snackbars" pattern) — a burst of errors queues up instead
 * of stacking illegibly or clobbering each other. */
export function ToastStack() {
  const dispatch = useAppDispatch()
  const queue = useAppSelector(selectNotificationQueue)
  const [current, setCurrent] = useState<AppNotification | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (queue.length > 0 && !current) {
      setCurrent(queue[0])
      setOpen(true)
    }
  }, [queue, current])

  const handleClose = (_event?: unknown, reason?: string): void => {
    if (reason === 'clickaway') return
    setOpen(false)
  }

  const handleExited = (): void => {
    if (current) dispatch(dismissed(current.id))
    setCurrent(null)
  }

  return (
    <Snackbar
      key={current?.id}
      open={open}
      autoHideDuration={AUTO_HIDE_MS}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      slotProps={{ transition: { onExited: handleExited } }}
    >
      {current ? (
        <Alert onClose={handleClose} severity={current.severity} variant="filled" className="shadow-lg">
          {current.message}
        </Alert>
      ) : undefined}
    </Snackbar>
  )
}
