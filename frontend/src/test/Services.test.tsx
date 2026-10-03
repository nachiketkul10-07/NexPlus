import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Services } from '../pages/Services';
import { createServiceApi, getServicesApi, previewGitHubRepositoryApi } from '../services/services';

vi.mock('../services/services', () => ({
  getServicesApi: vi.fn(),
  createServiceApi: vi.fn(),
  previewGitHubRepositoryApi: vi.fn(),
}));

describe('GitHub repository service onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getServicesApi).mockResolvedValue([]);
    vi.mocked(previewGitHubRepositoryApi).mockResolvedValue({
      full_name: 'owner/sample-app',
      repository_url: 'https://github.com/owner/sample-app',
      description: 'Example service',
      default_branch: 'main',
      language: 'Python',
      private: true,
      archived: false,
      manifest_files: ['pyproject.toml'],
    });
    vi.mocked(createServiceApi).mockResolvedValue({
      id: 'service-id',
      identifier: 'owner-sample-app',
      name: 'sample-app',
      environment: 'production',
      status: 'healthy',
      repository_url: 'https://github.com/owner/sample-app',
      created_at: new Date().toISOString(),
      ingest_key: 'pik_live_one_time_key',
    });
  });

  it('previews a repository, creates a linked service, and displays the one-time ingest key', async () => {
    render(<MemoryRouter><Services /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: 'Connect GitHub repository' }));
    fireEvent.change(screen.getByLabelText('GitHub repository URL'), {
      target: { value: 'https://github.com/owner/sample-app' },
    });
    fireEvent.change(screen.getByLabelText('Read-only token (private repos only)'), {
      target: { value: 'github_pat_temporary' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Fetch repository details' }));

    expect(await screen.findByText('owner/sample-app')).toBeInTheDocument();
    expect(screen.getByText(/pyproject.toml/)).toBeInTheDocument();
    expect(previewGitHubRepositoryApi).toHaveBeenCalledWith(
      'https://github.com/owner/sample-app', 'github_pat_temporary',
    );

    fireEvent.change(screen.getByLabelText('Running application URL (optional)'), {
      target: { value: 'https://api.example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create monitored service' }));

    await waitFor(() => expect(createServiceApi).toHaveBeenCalledWith(expect.objectContaining({
      repository_url: 'https://github.com/owner/sample-app',
      base_url: 'https://api.example.com',
      identifier: 'owner-sample-app',
    })));
    expect(await screen.findByText('pik_live_one_time_key')).toBeInTheDocument();
    expect(screen.getByText(/Send a first signal/)).toBeInTheDocument();
  });
});
