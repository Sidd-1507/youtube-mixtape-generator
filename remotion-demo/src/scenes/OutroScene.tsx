// src/scenes/OutroScene.tsx
// Scene 6 (48–55s): Closing card with project name + tech stack fading in line by line
import React from 'react';
import {AbsoluteFill, useCurrentFrame, interpolate, Easing} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';

interface Props { totalFrames: number }

const TECH_LINES = [
  {label: 'Python 3.12',  sub: 'Language'},
  {label: 'Pydub',        sub: 'Audio processing'},
  {label: 'FastAPI',      sub: 'REST backend'},
  {label: 'Streamlit',    sub: 'Frontend'},
  {label: 'FFmpeg 9',     sub: 'Video encoding'},
];

export const OutroScene: React.FC<Props> = ({totalFrames}) => {
  const frame   = useCurrentFrame();
  const fadeIn  = useFadeIn(15);
  const opacity = fadeIn;

  const lineOpacity = (i: number) =>
    interpolate(frame, [20 + i * 8, 35 + i * 8], [0, 1], {
      easing: Easing.ease,
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });

  const lineY = (i: number) =>
    interpolate(frame, [20 + i * 8, 35 + i * 8], [20, 0], {
      easing: Easing.out(Easing.cubic),
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });

  const ctaOpacity = interpolate(frame, [80, 100], [0, 1], {
    easing: Easing.ease,
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{opacity, background: '#0d0d1a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
      {/* Glow */}
      <div style={{
        position: 'absolute', width: 700, height: 700,
        background: 'radial-gradient(circle, rgba(124,58,237,0.25) 0%, transparent 70%)',
        top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
      }}/>

      {/* Title */}
      <div style={{
        fontSize: 72, fontWeight: 800, color: '#ffffff',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        letterSpacing: '-1px', marginBottom: 12, textAlign: 'center',
      }}>
        YouTube Mixtape Generator
      </div>
      <div style={{
        fontSize: 32, color: '#7c3aed',
        fontFamily: 'system-ui', marginBottom: 64, textAlign: 'center',
      }}>
        Built with:
      </div>

      {/* Tech stack */}
      <div style={{display: 'flex', gap: 28, flexWrap: 'wrap', justifyContent: 'center'}}>
        {TECH_LINES.map(({label, sub}, i) => (
          <div key={label} style={{
            opacity: lineOpacity(i),
            transform: `translateY(${lineY(i)}px)`,
            background: '#161630',
            borderRadius: 16, padding: '20px 32px',
            border: '1px solid #2a1366', textAlign: 'center',
            minWidth: 160,
          }}>
            <div style={{fontSize: 36, fontWeight: 800, color: '#a78bfa', fontFamily: 'system-ui'}}>
              {label}
            </div>
            <div style={{fontSize: 22, color: '#6b7280', marginTop: 8, fontFamily: 'system-ui'}}>
              {sub}
            </div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div style={{
        marginTop: 72, opacity: ctaOpacity, textAlign: 'center',
        fontSize: 28, color: '#6b7280', fontFamily: 'system-ui',
      }}>
        166 tests · 0 failures · production-ready
      </div>
    </AbsoluteFill>
  );
};
