import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { NexPulseLogo } from '../components/ui/NexPulseLogo';

export const Register: React.FC = () => {
  const navigate = useNavigate();
  const { register, isLoading, error, clearError } = useAuth();

  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [fullName, setFullName] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    clearError();

    if (!email.trim() || !password.trim() || !fullName.trim()) {
      setFormError('Please fill out all required fields.');
      return;
    }

    if (password.length < 8) {
      setFormError('Password must be at least 8 characters long.');
      return;
    }

    try {
      await register(email.trim(), password.trim(), fullName.trim());
      navigate('/app/overview', { replace: true });
    } catch {
      // Handled by AuthContext error
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
          <p className="text-xs text-[#A7A7A7]">Register new NexPulse operator credentials</p>
        </div>

        {/* Global Error */}
        {(error || formError) && (
          <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded text-xs text-[#EF4444]">
            {formError || error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Full Name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Jane Doe"
            required
          />

          <Input
            label="Email Address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="jane.doe@nexpulse.io"
            required
            autoComplete="email"
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Min. 8 characters"
            required
            autoComplete="new-password"
            helperText="Must be at least 8 characters long"
          />

          <Button type="submit" className="w-full" isLoading={isLoading}>
            Create Account & Sign In
          </Button>
        </form>

        {/* Login link */}
        <div className="text-center text-xs text-[#A7A7A7]">
          Already registered?{' '}
          <Link to="/login" className="text-[#E50039] hover:underline font-medium">
            Sign in to existing account
          </Link>
        </div>
      </div>
    </div>
  );
};

