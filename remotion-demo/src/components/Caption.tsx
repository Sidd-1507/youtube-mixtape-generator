// src/components/Caption.tsx
// Reusable bottom-third caption: step badge + main text + subtext
import React from 'react';

interface CaptionProps {
  step: string;
  text: string;
  sub?: string;
}

export const Caption: React.FC<CaptionProps> = ({step, text, sub}) => (
  <div style={{
    display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
    paddingLeft: 80, paddingRight: 80, gap: 8,
  }}>
    {/* Step badge */}
    <div style={{
      background: '#7c3aed',
      borderRadius: 8, padding: '6px 20px',
      fontSize: 22, fontWeight: 700, color: '#fff',
      fontFamily: 'system-ui, sans-serif',
      letterSpacing: 1, textTransform: 'uppercase',
      display: 'inline-block',
    }}>
      {step}
    </div>

    {/* Main text */}
    <div style={{
      background: 'rgba(13,13,26,0.80)',
      borderRadius: 12, padding: '12px 28px',
      fontSize: 38, fontWeight: 700, color: '#ffffff',
      fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>
      {text}
    </div>

    {/* Sub text */}
    {sub && (
      <div style={{
        background: 'rgba(13,13,26,0.65)',
        borderRadius: 8, padding: '8px 20px',
        fontSize: 26, color: '#9ca3af',
        fontFamily: 'system-ui, sans-serif',
      }}>
        {sub}
      </div>
    )}
  </div>
);
