import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, UserRole } from '../types';
import { loginApi, registerApi, getCurrentUserApi, logoutApi } from '../services/auth';
import { setOnUnauthorizedCallback } from '../services/api';
import { safeExtractErrorMessage } from '../lib/utils';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, fullName: string, role?: UserRole, invitationCode?: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(async () => {
    try { await logoutApi(); } catch { /* Clear local UI state even if the API is unavailable. */ }
    finally {
      setUser(null);
      setError(null);
    }
  }, []);

  useEffect(() => {
    setOnUnauthorizedCallback(logout);
  }, [logout]);

  useEffect(() => {
    let isMounted = true;

    async function initializeAuth() {
      try {
        const currentUser = await getCurrentUserApi();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch (err) {
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initializeAuth();

    return () => {
      isMounted = false;
    };
  }, [logout]);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const currentUser = await loginApi(email, pass);
      setUser(currentUser);
    } catch (err) {
      const msg = safeExtractErrorMessage(err);
      setError(msg);
      logout();
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, pass: string, fullName: string, role: UserRole = 'OPERATOR', invitationCode?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await registerApi(email, pass, fullName, role, invitationCode);
      // Auto-login upon registration
      await login(email, pass);
    } catch (err) {
      const msg = safeExtractErrorMessage(err);
      setError(msg);
      setIsLoading(false);
      throw err;
    }
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        register,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
