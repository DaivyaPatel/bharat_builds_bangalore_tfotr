import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import DriftTable from './DriftTable';

describe('DriftTable XSS safety (DL-023)', () => {
  it('renders a script-tag value as literal text, never executes it', () => {
    const maliciousComparison = {
      drifts: [
        {
          drift_id: 'test-xss-1',
          key: 'lambda:checkout/env_vars/EVIL_KEY',
          value_a: '<script>alert(1)</script>',
          value_b: 'safe_value',
          severity: 'critical',
          rule_id: 'R-TEST',
        },
      ],
    };

    render(<DriftTable comparison={maliciousComparison} />);

    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument();

    const scriptTags = document.querySelectorAll('script');
    const injectedScripts = Array.from(scriptTags).filter((el) =>
      el.textContent.includes('alert(1)')
    );
    expect(injectedScripts.length).toBe(0);
  });
});