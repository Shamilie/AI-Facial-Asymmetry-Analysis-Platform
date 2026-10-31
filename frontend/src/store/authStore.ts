import { create } from 'zustand';
import { api } from '@/services/api';
import { UserProfile } from '@/types';

interface ActiveContext {
  patientId?: string | null;
  patientCode?: string | null;
  fractureSide?: string | null;
  surgeryDate?: string | null;
  studyStatus?: string | null;
  visitId?: string | null;
  visitType?: string | null;
}

interface AuthState {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  activeContext: ActiveContext;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<UserProfile>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  setActiveContext: (ctx: Partial<ActiveContext>) => void;
  hasPermission: (perm: string) => boolean;
}

function loadStoredUser(): UserProfile | null {
  try {
    const raw = localStorage.getItem('fa_user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function loadStoredContext(): ActiveContext {
  try {
    const raw = localStorage.getItem('fa_active_ctx');
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: loadStoredUser(),
  token: localStorage.getItem('fa_access_token'),
  isAuthenticated: Boolean(localStorage.getItem('fa_access_token') && loadStoredUser()),
  activeContext: loadStoredContext(),

  login: async (email, password, rememberMe = true) => {
    const res = await api.post('/auth/login', { email, password, remember_me: rememberMe });
    const { access_token, refresh_token, user } = res.data.data;
    localStorage.setItem('fa_access_token', access_token);
    localStorage.setItem('fa_refresh_token', refresh_token);
    localStorage.setItem('fa_user', JSON.stringify(user));
    set({ user, token: access_token, isAuthenticated: true });
    return user;
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // ignore network failure on logout
    }
    localStorage.removeItem('fa_access_token');
    localStorage.removeItem('fa_refresh_token');
    localStorage.removeItem('fa_user');
    set({ user: null, token: null, isAuthenticated: false });
  },

  refreshProfile: async () => {
    try {
      const res = await api.get('/auth/me');
      const user = res.data.data;
      localStorage.setItem('fa_user', JSON.stringify(user));
      set({ user, isAuthenticated: true });
    } catch {
      set({ user: null, token: null, isAuthenticated: false });
    }
  },

  setActiveContext: (ctx) => {
    const merged = { ...get().activeContext, ...ctx };
    localStorage.setItem('fa_active_ctx', JSON.stringify(merged));
    set({ activeContext: merged });
  },

  hasPermission: (perm) => {
    const u = get().user;
    if (!u) return false;
    if (u.is_superuser) return true;
    return u.permissions?.includes(perm) ?? false;
  },
}));
