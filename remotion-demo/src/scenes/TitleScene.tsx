// src/scenes/TitleScene.tsx
// Scene 1 (0–4s): Title card — fades in, text appears line by line
import React from 'react';
import {AbsoluteFill, useCurrentFrame, interpolate, Easing} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';

interface Props { totalFrames: number }

export const TitleScene: React.FC<Props> = ({totalFrames}) => {
  const frame    = useCurrentFrame();
  const fadeIn   = useFadeIn(20);
  const fadeOut  = useFadeOut(totalFrames, 15);
  const opacity  = Math.min(fadeIn, fadeOut);

  // Title slides up
  const titleY = interpolate(frame, [0, 25], [40, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: 'clamp',
  });

  // Subtitle appears a little later
  const subOpacity = interpolate(frame, [20, 45], [0, 1], {
    easing: Easing.ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Pills appear even later
  const pillOpacity = interpolate(frame, [35, 60], [0, 1], {
    easing: Easing.ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const TECH = ['Python', 'Pydub', 'FastAPI', 'Streamlit', 'FFmpeg'];

  return (
    <AbsoluteFill style={{opacity, background: '#0d0d1a', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 0}}>
      {/* Violet glow behind */}
      <div style={{
        position: 'absolute', width: 800, height: 800,
        background: 'radial-gradient(circle, rgba(124,58,237,0.35) 0%, transparent 70%)',
        top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
      }}/>

      {/* Main title */}
      <div style={{
        transform: `translateY(${titleY}px)`,
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: 92, fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 800, color: '#ffffff', lineHeight: 1.1,
          letterSpacing: '-2px',
        }}>
          YouTube Mixtape
        </div>
        <div style={{
          fontSize: 92, fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 800, color: '#7c3aed', lineHeight: 1.1,
          letterSpacing: '-2px',
        }}>
          Generator
        </div>
      </div>

      {/* Subtitle */}
      <div style={{
        marginTop: 28, opacity: subOpacity,
        fontSize: 34, color: '#9ca3af',
        fontFamily: 'system-ui, sans-serif', fontWeight: 400,
        letterSpacing: '0.5px',
      }}>
        Automated audio&nbsp;·&nbsp;timestamps&nbsp;·&nbsp;video pipeline in Python
      </div>

      {/* Tech pills */}
      <div style={{display: 'flex', gap: 16, marginTop: 56, opacity: pillOpacity}}>
        {TECH.map((t) => (
          <div key={t} style={{
            padding: '10px 24px',
            borderRadius: 24, background: '#2a1366',
            color: '#a78bfa', fontSize: 26,
            fontFamily: 'system-ui, sans-serif', fontWeight: 600,
          }}>
            {t}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};
