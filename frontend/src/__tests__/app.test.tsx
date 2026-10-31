import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  EmptyState,
  KpiCard,
  PageHeader,
  ResearchDisclaimerBanner,
  StatusBadge,
} from '@/components/common/ui';

describe('AI Facial Asymmetry Analysis Platform — Frontend Core Components', () => {
  it('renders the mandatory non-diagnostic ResearchDisclaimerBanner', () => {
    render(<ResearchDisclaimerBanner />);
    expect(screen.getByText(/Research Measurement & Documentation Only/i)).toBeDefined();
    expect(
      screen.getByText(/do not constitute a medical diagnosis/i)
    ).toBeDefined();
  });

  it('renders StatusBadge for clinical and measurement states', () => {
    render(
      <div>
        <StatusBadge status="ReviewRequired" />
        <StatusBadge status="Unscaled" />
        <StatusBadge status="Validated" />
        <StatusBadge status="NotIdentifiable" />
      </div>
    );
    expect(screen.getByText('ReviewRequired')).toBeDefined();
    expect(screen.getByText('Unscaled')).toBeDefined();
    expect(screen.getByText('Validated')).toBeDefined();
    expect(screen.getByText('NotIdentifiable')).toBeDefined();
  });

  it('renders KpiCard and PageHeader with clinical research titles', () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="Quantitative Facial & Mandibular Asymmetry Measurements"
          subtitle="Bilateral linear and angular metrics"
        />
        <KpiCard label="Mean Asymmetry Index" value="4.82 %" subtitle="|R - L| / (R + L) × 100" />
        <EmptyState title="No pending reviews" description="All visits reviewed" />
      </MemoryRouter>
    );
    expect(
      screen.getByText('Quantitative Facial & Mandibular Asymmetry Measurements')
    ).toBeDefined();
    expect(screen.getByText('4.82 %')).toBeDefined();
    expect(screen.getByText('No pending reviews')).toBeDefined();
  });
});
