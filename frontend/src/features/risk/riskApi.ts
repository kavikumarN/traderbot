import { apiSlice } from '@/api/apiSlice'
import type {
  CreateRiskRuleRequest,
  PositionSizeRequest,
  PositionSizeResponse,
  RiskRule,
  RiskState,
  SetEmergencyStopRequest,
  UpdateRiskRuleRequest,
} from './types'

export const riskApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    getRiskState: builder.query<RiskState, void>({
      query: () => ({ url: '/api/v1/risk/state', method: 'GET' }),
      providesTags: ['RiskState'],
    }),

    listRiskRules: builder.query<RiskRule[], void>({
      query: () => ({ url: '/api/v1/risk/rules', method: 'GET' }),
      providesTags: (result) =>
        result
          ? [...result.map((r) => ({ type: 'RiskRule' as const, id: r.id })), { type: 'RiskRule' as const, id: 'LIST' }]
          : [{ type: 'RiskRule' as const, id: 'LIST' }],
    }),

    createRiskRule: builder.mutation<RiskRule, CreateRiskRuleRequest>({
      query: (body) => ({ url: '/api/v1/risk/rules', method: 'POST', data: body }),
      invalidatesTags: [{ type: 'RiskRule', id: 'LIST' }],
    }),

    updateRiskRule: builder.mutation<RiskRule, { ruleId: string; body: UpdateRiskRuleRequest }>({
      query: ({ ruleId, body }) => ({ url: `/api/v1/risk/rules/${ruleId}`, method: 'PATCH', data: body }),
      invalidatesTags: (_result, _error, { ruleId }) => [
        { type: 'RiskRule', id: ruleId },
        { type: 'RiskRule', id: 'LIST' },
      ],
    }),

    deleteRiskRule: builder.mutation<void, string>({
      query: (ruleId) => ({ url: `/api/v1/risk/rules/${ruleId}`, method: 'DELETE' }),
      invalidatesTags: [{ type: 'RiskRule', id: 'LIST' }],
    }),

    setEmergencyStop: builder.mutation<RiskState, SetEmergencyStopRequest>({
      query: (body) => ({ url: '/api/v1/risk/emergency-stop', method: 'POST', data: body }),
      invalidatesTags: ['RiskState'],
    }),

    resetCircuitBreaker: builder.mutation<RiskState, void>({
      query: () => ({ url: '/api/v1/risk/circuit-breaker/reset', method: 'POST' }),
      invalidatesTags: ['RiskState'],
    }),

    rearmDeRisk: builder.mutation<RiskState, void>({
      query: () => ({ url: '/api/v1/risk/de-risk/rearm', method: 'POST' }),
      invalidatesTags: ['RiskState'],
    }),

    calculatePositionSize: builder.mutation<PositionSizeResponse, PositionSizeRequest>({
      query: (body) => ({ url: '/api/v1/risk/position-size', method: 'POST', data: body }),
    }),
  }),
})

export const {
  useGetRiskStateQuery,
  useListRiskRulesQuery,
  useCreateRiskRuleMutation,
  useUpdateRiskRuleMutation,
  useDeleteRiskRuleMutation,
  useSetEmergencyStopMutation,
  useResetCircuitBreakerMutation,
  useRearmDeRiskMutation,
  useCalculatePositionSizeMutation,
} = riskApi
