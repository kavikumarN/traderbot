import type { TokenPair, TokenResponseDto } from './types'

export function mapTokenResponse(dto: TokenResponseDto): TokenPair {
  return {
    accessToken: dto.access_token,
    accessTokenExpiresAt: dto.access_token_expires_at,
    refreshToken: dto.refresh_token,
    refreshTokenExpiresAt: dto.refresh_token_expires_at,
  }
}
