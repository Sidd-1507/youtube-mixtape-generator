// src/scenes/MixtapeScene.tsx
// Scene 3 (12–22s): Merged audio + waveform animation proving merge worked
import React from 'react';
import {AbsoluteFill, Audio, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';
import {Caption} from '../components/Caption';

interface Props { totalFrames: number }

export const MixtapeScene: React.FC<Props> = ({totalFrames}) => {
  const frame   = useCurrentFrame();
  const fadeIn  = useFadeIn(15);
  const fadeOut = useFadeOut(totalFrames, 15);
  const opacity = Math.min(fadeIn, fadeOut);

  const captionY = interpolate(frame, [10, 30], [60, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // Animated waveform bars — 32 bars, each oscillates at different phase
  const BAR_COUNT = 32;
  const bars = Array.from({length: BAR_COUNT}, (_, i) => {
    const phase = (i / BAR_COUNT) * Math.PI * 2;
    const freq  = 0.08 + (i % 5) * 0.02;
    const amp   = 40 + (i % 3) * 25;
    const h = Math.abs(Math.sin(frame * freq + phase) * amp) + 8;
    return h;
  });

  // Stats cards slide in
  const statsOpacity = interpolate(frame, [20, 45], [0, 1], {
    easing: Easing.ease,
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{opacity, background: '#0d0d1a'}}>
      {/* Subtle audio — play first 10s of merged audio */}
      <Audio src={staticFile('merged.mp3')} startFrom={0} endAt={totalFrames} volume={0.8} />

      {/* Top label */}
      <div style={{
        position: 'absolute', top: 60, left: 80,
        fontSize: 28, color: '#7c3aed',
        fontFamily: 'system-ui, sans-serif', fontWeight: 700,
        letterSpacing: 2, textTransform: 'uppercase',
      }}>
        ▶ Now Playing — Merged Mixtape
      </div>

      {/* Track info */}
      <div style={{
        position: 'absolute', top: 110, left: 80,
        fontSize: 52, color: '#ffffff',
        fontFamily: 'system-ui, sans-serif', fontWeight: 800,
      }}>
        Storynory Audio Stories
      </div>
      <div style={{
        position: 'absolute', top: 178, left: 80,
        fontSize: 32, color: '#9ca3af',
        fontFamily: 'system-ui, sans-serif',
      }}>
        2 tracks · 27 min 17 s · crossfade 2 s
      </div>

      {/* Waveform visualizer */}
      <div style={{
        position: 'absolute', top: 260, left: 0, right: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 10, height: 220,
      }}>
        {bars.map((h, i) => (
          <div
            key={i}
            style={{
              width: 36,
              height: h,
              borderRadius: 4,
              background: `linear-gradient(to top, #7c3aed, #a78bfa)`,
              transition: 'height 0.05s ease',
              boxShadow: `0 0 ${h/3}px rgba(124,58,237,0.4)`,
            }}
          />
        ))}
      </div>

      {/* Stats row */}
      <div style={{
        position: 'absolute', top: 520, left: 80, right: 80,
        display: 'flex', gap: 40, opacity: statsOpacity,
      }}>
        {[
          {val: '2',        label: 'Tracks merged'},
          {val: '27:17',    label: 'Total duration'},
          {val: '2 000 ms', label: 'Crossfade'},
          {val: '−3.0 dBFS',label: 'Normalize target'},
          {val: '37.5 MB',  label: 'Output size'},
        ].map(({val, label}) => (
          <div key={label} style={{
            flex: 1, background: '#161630', borderRadius: 16,
            padding: '28px 24px', textAlign: 'center',
            border: '1px solid #2a1366',
          }}>
            <div style={{fontSize: 40, fontWeight: 800, color: '#a78bfa', fontFamily: 'system-ui'}}>
              {val}
            </div>
            <div style={{fontSize: 22, color: '#6b7280', marginTop: 8, fontFamily: 'system-ui'}}>
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Gradient + caption */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 220,
        background: 'linear-gradient(to top, rgba(13,13,26,0.95) 0%, transparent 100%)',
      }}/>
      <div style={{position: 'absolute', bottom: 60, left: 0, right: 0, transform: `translateY(${captionY}px)`}}>
        <Caption
          step="Step 2"
          text="Merge tracks with crossfade using Pydub"
          sub="2-second crossfade · normalized loudness · single merged.mp3"
        />
      </div>
    </AbsoluteFill>
  );
};
