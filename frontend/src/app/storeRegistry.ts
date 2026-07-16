import type { AppStore } from '@/app/store'

/**
 * Lets modules outside the React tree (the Axios client's interceptors, in
 * particular) reach the Redux store without creating an import cycle:
 * `store.ts` -> `apiSlice` -> `axiosClient` -> `store.ts` would otherwise be
 * circular. `axiosClient` imports this leaf module instead; `store.ts`
 * registers itself here once, after it's constructed.
 */
let currentStore: AppStore | undefined

export function registerStore(store: AppStore): void {
  currentStore = store
}

export function getStore(): AppStore {
  if (!currentStore) {
    throw new Error('Redux store was used before registerStore() ran.')
  }
  return currentStore
}
