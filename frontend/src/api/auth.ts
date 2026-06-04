// auth.ts
import api, { tokenStore } from './client';
import type { AuthTokens, User } from '@/types';

export const authApi = {
  async login(email: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/login', { email, password });
    tokenStore.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  async getMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },

  logout() {
    tokenStore.clearTokens();
  },
};
