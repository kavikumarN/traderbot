import { configureStore } from '@reduxjs/toolkit'
import { apiSlice } from '@/api/apiSlice'
import authReducer from '@/features/auth/authSlice'
import notificationsReducer from '@/notifications/notificationsSlice'
import themeReducer from '@/theme/themeSlice'
import { registerStore } from './storeRegistry'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    theme: themeReducer,
    notifications: notificationsReducer,
    [apiSlice.reducerPath]: apiSlice.reducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(apiSlice.middleware),
})

// Axios interceptors (outside the React tree) reach the store through this
// registry — see `app/storeRegistry.ts` for why it isn't a direct import.
registerStore(store)

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
export type AppStore = typeof store
