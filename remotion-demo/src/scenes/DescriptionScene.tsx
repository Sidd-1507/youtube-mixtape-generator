// src/scenes/DescriptionScene.tsx
// Scene 4 (22–32s): Description card — timestamp lines appear one by one staggered 0.3s
import React from 'react';
import {AbsoluteFill, useCurrentFrame, interpolate, Easing} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';
import {Caption} from '../components/Caption';

interface Props { totalFrames: number }

const FPS = 30;

const DESCRIPTION_LINES = [
  {text: '🎵 Storynory Audio Stories — Mixtape', type: 'header'},
  {text: '',                                      type: 'blank'},
  {text: 'Two classic tales from Storynory, back to back.', type: 'body'},
  {text: '',                                      type: 'blank'},
  {text: '0:00',  track: '01-stella-magic-mirror-16',         type: 'timestamp'},
  {text: '15:17', track: 'journey-to-the-west-crown-that-hurt-16', type: 'timestamp'},
  {text: '',                                      type: 'blank'},
  {text: '#storynory #audiobook #storiesforchildren #mixtape', type: 'footer'},
];

export const DescriptionScene: React.FC<Props> = ({totalFrames}) => {
  const frame   = useCurrentFrame();
  const fadeIn  = useFadeIn(15);
  const fadeOut = useFadeOut(totalFrames, 15);
  const opacity = Math.min(fadeIn, fadeOut);

  // Description card slides up
  const cardY = interpolate(frame, [0, 20], [30, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateRight: 'clamp',
  });

  const captionY = interpolate(frame, [10, 30], [60, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // How to check if a line has appeared yet (staggered by 0.3s = 9 frames)
  const lineVisible = (index: number) => {
    const staggerFrames = 9; // 0.3s at 30fps
    return frame >= 15 + index * staggerFrames;
  };

  const lineOpacity = (index: number) => {
    const staggerFrames = 9;
    const startFrame = 15 + index * staggerFrames;
    return interpolate(frame, [startFrame, startFrame + 12], [0, 1], {
      easing: Easing.ease,
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
  };

  const lineY = (index: number) => {
    const staggerFrames = 9;
    const startFrame = 15 + index * staggerFrames;
    return interpolate(frame, [startFrame, startFrame + 14], [16, 0], {
      easing: Easing.out(Easing.cubic),
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
  };

  return (
    <AbsoluteFill style={{opacity, background: '#0d0d1a'}}>
      {/* Top label */}
      <div style={{
        position: 'absolute', top: 48, left: 80,
        fontSize: 28, color: '#7c3aed',
        fontFamily: 'system-ui, sans-serif', fontWeight: 700,
        letterSpacing: 2, textTransform: 'uppercase',
      }}>
        📝 Auto-generated Description
      </div>

      {/* Description card */}
      <div style={{
        position: 'absolute', top: 110, left: 80, right: 80,
        background: '#161630',
        borderRadius: 20, padding: '48px 56px',
        border: '1px solid #2a1366',
        transform: `translateY(${cardY}px)`,
        minHeight: 520,
      }}>
        {DESCRIPTION_LINES.map((line, i) => {
          if (line.type === 'blank') return <div key={i} style={{height: 16}} />;

          const lOpacity = lineOpacity(i);
          const lY = lineY(i);

          if (line.type === 'timestamp') {
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'baseline', gap: 20,
                opacity: lOpacity, transform: `translateY(${lY}px)`,
                marginBottom: 12,
              }}>
                <span style={{
                  fontSize: 40, fontWeight: 800, color: '#ffd700',
                  fontFamily: 'monospace', minWidth: 80,
                }}>
                  {line.text}
                </span>
                <span style={{fontSize: 36, color: '#e2e8f0', fontFamily: 'system-ui'}}>
                  {line.track}
                </span>
              </div>
            );
          }

          if (line.type === 'header') {
            return (
              <div key={i} style={{
                fontSize: 44, fontWeight: 800, color: '#ffffff',
                fontFamily: 'system-ui', marginBottom: 4,
                opacity: lOpacity, transform: `translateY(${lY}px)`,
              }}>
                {line.text}
              </div>
            );
          }

          if (line.type === 'footer') {
            return (
              <div key={i} style={{
                fontSize: 28, color: '#7c3aed',
                fontFamily: 'system-ui', marginTop: 8,
                opacity: lOpacity, transform: `translateY(${lY}px)`,
              }}>
                {line.text}
              </div>
            );
          }

          return (
            <div key={i} style={{
              fontSize: 32, color: '#9ca3af',
              fontFamily: 'system-ui', marginBottom: 4,
              opacity: lOpacity, transform: `translateY(${lY}px)`,
            }}>
              {line.text}
            </div>
          );
        })}
      </div>

      {/* Gradient + caption */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 220,
        background: 'linear-gradient(to top, rgba(13,13,26,0.95) 0%, transparent 100%)',
      }}/>
      <div style={{position: 'absolute', bottom: 60, left: 0, right: 0, transform: `translateY(${captionY}px)`}}>
        <Caption
          step="Step 3"
          text="Auto-generate YouTube description with timestamps"
          sub="Clickable timestamps · custom header & footer · zero manual editing"
        />
      </div>
    </AbsoluteFill>
  );
};
