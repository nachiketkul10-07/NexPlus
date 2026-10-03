import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { NexPulseLogo } from '../components/ui/NexPulseLogo';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading, error, clearError } = useAuth();

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const registrationEnabled = import.meta.env.DEV || import.meta.env.VITE_PUBLIC_REGISTRATION_ENABLED === 'true';

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/app/overview';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    clearError();

    if (!email.trim() || !password.trim()) {
      setFormError('Please enter both email address and password.');
      return;
    }

    try {
      await login(email.trim(), password.trim());
      navigate(from, { replace: true });
    } catch {
      // Error handled by AuthContext error state
    }
  };

  return (
    <div className="min-h-screen bg-[#191919] text-[#F7F7F7] flex items-center justify-center p-4 selection:bg-[#E50039] selection:text-white">
      <div className="w-full max-w-md bg-[#1F1F1F] border border-[#333333] rounded p-8 space-y-6 shadow-2xl">
        {/* Header */}
        <div className="space-y-3 text-center flex flex-col items-center">
          <Link to="/">
            <NexPulseLogo variant="hero" showTagline={true} />
          </Link>
          <p className="text-xs text-[#A7A7A7]">Sign in to your NexPulse engineering workspace</p>
        </div>

        {/* Global Error Notice */}
        {(error || formError) && (
          <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded text-xs text-[#EF4444]">
            {formError || error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email Address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="operator@nexpulse.io"
            required
            autoComplete="email"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            required
            autoComplete="current-password"
          />

          <Button type="submit" className="w-full" isLoading={isLoading}>
            Authenticate Session
          </Button>
        </form>

        {/* Register link */}
        {registrationEnabled && <div className="text-center text-xs text-[#A7A7A7]">
          Need a NexPulse operator account?{' '}
          <Link to="/register" className="text-[#E50039] hover:underline font-medium">
            Register new account
          </Link>
        </div>}
      </div>
    </div>
  );
};

