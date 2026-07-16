import { apiSlice } from '@/api/apiSlice'
import type {
  AuditLogEntry,
  Order,
  OrderListResponse,
  PlaceLimitOrderRequest,
  PlaceMarketOrderRequest,
  PlaceStopOrderRequest,
} from './types'

export const ordersApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    listOpenOrders: builder.query<Order[], void>({
      query: () => ({ url: '/api/v1/trading/orders/open', method: 'GET' }),
      providesTags: (result) =>
        result
          ? [...result.map((o) => ({ type: 'Order' as const, id: o.id })), { type: 'Order' as const, id: 'OPEN' }]
          : [{ type: 'Order' as const, id: 'OPEN' }],
    }),

    listOrderHistory: builder.query<OrderListResponse, { offset: number; limit: number }>({
      query: ({ offset, limit }) => ({
        url: '/api/v1/trading/orders',
        method: 'GET',
        params: { offset, limit },
      }),
      providesTags: [{ type: 'Order', id: 'HISTORY' }],
    }),

    getOrder: builder.query<Order, string>({
      query: (orderId) => ({ url: `/api/v1/trading/orders/${orderId}`, method: 'GET' }),
      providesTags: (_result, _error, orderId) => [{ type: 'Order', id: orderId }],
    }),

    getOrderAuditLog: builder.query<AuditLogEntry[], string>({
      query: (orderId) => ({ url: `/api/v1/trading/orders/${orderId}/audit-log`, method: 'GET' }),
    }),

    placeMarketOrder: builder.mutation<Order, PlaceMarketOrderRequest>({
      query: (body) => ({ url: '/api/v1/trading/orders/market', method: 'POST', data: body }),
      invalidatesTags: [{ type: 'Order', id: 'OPEN' }, { type: 'Order', id: 'HISTORY' }],
    }),

    placeLimitOrder: builder.mutation<Order, PlaceLimitOrderRequest>({
      query: (body) => ({ url: '/api/v1/trading/orders/limit', method: 'POST', data: body }),
      invalidatesTags: [{ type: 'Order', id: 'OPEN' }, { type: 'Order', id: 'HISTORY' }],
    }),

    placeStopOrder: builder.mutation<Order, PlaceStopOrderRequest>({
      query: (body) => ({ url: '/api/v1/trading/orders/stop', method: 'POST', data: body }),
      invalidatesTags: [{ type: 'Order', id: 'OPEN' }, { type: 'Order', id: 'HISTORY' }],
    }),

    cancelOrder: builder.mutation<Order, string>({
      query: (orderId) => ({ url: `/api/v1/trading/orders/${orderId}/cancel`, method: 'POST' }),
      invalidatesTags: (_result, _error, orderId) => [
        { type: 'Order', id: orderId },
        { type: 'Order', id: 'OPEN' },
        { type: 'Order', id: 'HISTORY' },
      ],
    }),

    syncOrder: builder.mutation<Order, string>({
      query: (orderId) => ({ url: `/api/v1/trading/orders/${orderId}/sync`, method: 'POST' }),
      invalidatesTags: (_result, _error, orderId) => [
        { type: 'Order', id: orderId },
        { type: 'Order', id: 'OPEN' },
        { type: 'Order', id: 'HISTORY' },
      ],
    }),
  }),
})

export const {
  useListOpenOrdersQuery,
  useListOrderHistoryQuery,
  useGetOrderQuery,
  useGetOrderAuditLogQuery,
  usePlaceMarketOrderMutation,
  usePlaceLimitOrderMutation,
  usePlaceStopOrderMutation,
  useCancelOrderMutation,
  useSyncOrderMutation,
} = ordersApi
