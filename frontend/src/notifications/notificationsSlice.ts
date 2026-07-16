import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { RootState } from '@/app/store'

export type NotificationSeverity = 'success' | 'error' | 'info' | 'warning'

export interface AppNotification {
  id: string
  message: string
  severity: NotificationSeverity
}

interface NotificationsState {
  queue: AppNotification[]
}

const initialState: NotificationsState = { queue: [] }

let nextId = 0

const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    notify: {
      reducer(state, action: PayloadAction<AppNotification>) {
        state.queue.push(action.payload)
      },
      prepare(message: string, severity: NotificationSeverity = 'info') {
        nextId += 1
        return { payload: { id: `notification-${nextId}`, message, severity } }
      },
    },
    dismissed(state, action: PayloadAction<string>) {
      state.queue = state.queue.filter((item) => item.id !== action.payload)
    },
  },
})

export const { notify, dismissed } = notificationsSlice.actions
export default notificationsSlice.reducer

export const notifySuccess = (message: string) => notify(message, 'success')
export const notifyError = (message: string) => notify(message, 'error')
export const notifyInfo = (message: string) => notify(message, 'info')
export const notifyWarning = (message: string) => notify(message, 'warning')

export const selectNotificationQueue = (state: RootState) => state.notifications.queue
