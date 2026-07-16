import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { GuestRoute } from '@/components/routing/GuestRoute'
import { ProtectedRoute } from '@/components/routing/ProtectedRoute'
import DashboardPage from '@/features/dashboard/pages/DashboardPage'
import LoginPage from '@/features/auth/pages/LoginPage'
import RegisterPage from '@/features/auth/pages/RegisterPage'
import BacktestingPage from '@/features/backtesting/pages/BacktestingPage'
import InsightsPage from '@/features/insights/pages/InsightsPage'
import OrdersPage from '@/features/orders/pages/OrdersPage'
import PortfolioPage from '@/features/portfolio/pages/PortfolioPage'
import RiskPage from '@/features/risk/pages/RiskPage'
import StrategiesPage from '@/features/strategies/pages/StrategiesPage'
import NotFoundPage from '@/pages/NotFoundPage'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      <Route
        path="/login"
        element={
          <GuestRoute>
            <LoginPage />
          </GuestRoute>
        }
      />
      <Route
        path="/register"
        element={
          <GuestRoute>
            <RegisterPage />
          </GuestRoute>
        }
      />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/strategies" element={<StrategiesPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/backtesting" element={<BacktestingPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/insights" element={<InsightsPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
