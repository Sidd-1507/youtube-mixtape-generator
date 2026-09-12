// src/scenes/UploadScene.tsx
// Scene 2 (4–12s): Upload card screenshot with Ken-Burns zoom + caption overlay
import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame, interpolate, Easing} from 'remotion';
import {useFadeIn, useFadeOut} from '../MixtapeDemo';
import {Caption} from '../components/Caption';

interface Props { totalFrames: number }

export const UploadScene: React.FC<Props> = ({totalFrames}) => {
  const frame   = useCurrentFrame();
  const fadeIn  = useFadeIn(15);
  const fadeOut = useFadeOut(totalFrames, 15);
  const opacity = Math.min(fadeIn, fadeOut);

  // Ken-Burns: subtle zoom from 1.0 to 1.04 over the whole scene
  const scale = interpolate(frame, [0, totalFrames], [1.0, 1.04], {
    extrapolateRight: 'clamp',
  });

  // Caption slides up from bottom
  const captionY = interpolate(frame, [10, 30], [60, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{opacity}}>
      {/* Full-screen screenshot */}
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: 'center center'}}>
        <Img
          src={staticFile('upload.png')}
          style={{width: '100%', height: '100%', objectFit: 'cover'}}
        />
      </AbsoluteFill>

      {/* Dark gradient at bottom for caption legibility */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: 260,
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, transparent 100%)',
      }}/>

      {/* Caption */}
      <div style={{position: 'absolute', bottom: 60, left: 0, right: 0, transform: `translateY(${captionY}px)`}}>
        <Caption
          step="Step 1"
          text="Upload raw audio tracks"
          sub="Two Storynory episodes · 27.3 minutes total"
        />
      </div>
    </AbsoluteFill>
  );
};
