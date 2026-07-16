import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import { store } from './app/store'
import { ErrorBoundary } from './components/feedback/ErrorBoundary'
import { ToastStack } from './components/feedback/ToastStack'
import './index.css'
import { ThemeModeProvider } from './theme/ThemeModeProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <Provider store={store}>
        <ThemeModeProvider>
          <BrowserRouter>
            <App />
            <ToastStack />
          </BrowserRouter>
        </ThemeModeProvider>
      </Provider>
    </ErrorBoundary>
  </StrictMode>,
)
