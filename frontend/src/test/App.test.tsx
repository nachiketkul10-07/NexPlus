import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { NexPulseLogo } from '../components/ui/NexPulseLogo';

describe('NexPulse Frontend Component & Page Suite', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('renders NexPulse homepage by default at root path with branding and product statement', async () => {
    render(<App />);
    expect(await screen.findByText('Know when your')).toBeInTheDocument();
    expect(screen.getByText('systems lose the signal.')).toBeInTheDocument();
    expect(screen.getAllByText(/OBSERVE.*DETECT.*RESPOND/).length).toBeGreaterThan(0);
  });

  it('renders NexPulse logo component in hero and sidebar variants', () => {
    const { container } = render(<NexPulseLogo variant="hero" />);
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByText('Nex')).toBeInTheDocument();
    expect(screen.getByText('Pulse')).toBeInTheDocument();
  });

  it('renders Button component with correct brand styling', () => {
    render(<Button variant="primary">Launch Platform</Button>);
    const button = screen.getByRole('button', { name: 'Launch Platform' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveClass('bg-[#E50039]');
  });

  it('renders Badge component with healthy status variant', () => {
    render(<Badge variant="healthy">HEALTHY</Badge>);
    const badge = screen.getByText('HEALTHY');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('text-[#10B981]');
  });

  it('renders StatusIndicator component correctly', () => {
    render(<StatusIndicator status="healthy" />);
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('renders EmptyState component with explanation', () => {
    render(
      <EmptyState
        title="No Monitored Services"
        description="No services have been registered yet."
      />
    );
    expect(screen.getByText('No Monitored Services')).toBeInTheDocument();
    expect(screen.getByText('No services have been registered yet.')).toBeInTheDocument();
  });

  it('renders ErrorState component with status code and retry action', () => {
    render(
      <ErrorState
        title="Access Denied"
        message="Insufficient permissions"
        statusCode={403}
      />
    );
    expect(screen.getByText('Access Denied')).toBeInTheDocument();
    expect(screen.getByText('403')).toBeInTheDocument();
  });
});

