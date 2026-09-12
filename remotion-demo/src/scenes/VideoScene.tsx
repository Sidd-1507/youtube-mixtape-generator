// src/scenes/VideoScene.tsx
// Scene 5 (32–48s): Full MP4 video output plays with caption overlay
import React from 'react';
import {
  AbsoluteFill, OffthreadVideo, staticFile,
  useCurrentFrame, interpolate, Easing,
} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';
import {Caption} from '../components/Caption';

interface Props { totalFrames: number }

export const VideoScene: React.FC<Props> = ({totalFrames}) => {
  const frame   = useCurrentFrame();
  const fadeIn  = useFadeIn(15);
  const fadeOut = useFadeOut(totalFrames, 15);
  const opacity = Math.min(fadeIn, fadeOut);

  const captionY = interpolate(frame, [10, 30], [60, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // "LIVE" badge pulse
  const pulseBadge = Math.sin(frame * 0.2) * 0.3 + 0.7;

  return (
    <AbsoluteFill style={{opacity, background: '#000000'}}>
      {/* The actual rendered MP4 video — shows background image + audio playing */}
      <OffthreadVideo
        src={staticFile('video-output.mp4')}
        style={{width: '100%', height: '100%', objectFit: 'cover'}}
        startFrom={0}
        endAt={totalFrames}
        volume={0.7}
      />

      {/* "RENDERED OUTPUT" badge top-right */}
      <div style={{
        position: 'absolute', top: 40, right: 60,
        background: 'rgba(124,58,237,0.9)', borderRadius: 12,
        padding: '10px 24px',
        display: 'flex', alignItems: 'center', gap: 12,
        opacity: pulseBadge,
      }}>
        <div style={{
          width: 14, height: 14, borderRadius: '50%',
          background: '#ff4444',
          boxShadow: '0 0 8px 2px rgba(255,68,68,0.7)',
        }}/>
        <span style={{
          color: '#fff', fontSize: 24, fontWeight: 700,
          fontFamily: 'system-ui, sans-serif', letterSpacing: 1,
        }}>
          RENDERED OUTPUT
        </span>
      </div>

      {/* Gradient + caption */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 280,
        background: 'linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 100%)',
      }}/>
      <div style={{position: 'absolute', bottom: 60, left: 0, right: 0, transform: `translateY(${captionY}px)`}}>
        <Caption
          step="Step 4"
          text="Convert audio to video with FFmpeg"
          sub="H.264 · AAC 192k · 1920×1080 · YouTube-ready MP4"
        />
      </div>
    </AbsoluteFill>
  );
};
