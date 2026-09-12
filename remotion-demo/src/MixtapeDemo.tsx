// src/MixtapeDemo.tsx
// Master composition — sequences all 6 scenes with crossfade transitions
import React from 'react';
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from 'remotion';

import {TitleScene}       from './scenes/TitleScene';
import {UploadScene}      from './scenes/UploadScene';
import {MixtapeScene}     from './scenes/MixtapeScene';
import {DescriptionScene} from './scenes/DescriptionScene';
import {VideoScene}       from './scenes/VideoScene';
import {OutroScene}       from './scenes/OutroScene';

const FPS = 30;

// Scene durations in frames
const DUR = {
  title:       4  * FPS,
  upload:      8  * FPS,
  mixtape:     10 * FPS,
  description: 10 * FPS,
  video:       16 * FPS,
  outro:       7  * FPS,
};

// Start frame of each scene
const START = {
  title:       0,
  upload:      DUR.title,
  mixtape:     DUR.title + DUR.upload,
  description: DUR.title + DUR.upload + DUR.mixtape,
  video:       DUR.title + DUR.upload + DUR.mixtape + DUR.description,
  outro:       DUR.title + DUR.upload + DUR.mixtape + DUR.description + DUR.video,
};

const FADE = 15; // 0.5s crossfade overlap at each cut

/** Per-scene fade-in: opacity goes 0 → 1 over the first FADE frames */
export const useFadeIn = (fadeDuration = FADE) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [0, fadeDuration], [0, 1], {
    easing: Easing.ease,
    extrapolateRight: 'clamp',
  });
};

/** Per-scene fade-out: opacity 1 → 0 over the last FADE frames of `totalDur` */
export const useFadeOut = (totalDur: number, fadeDuration = FADE) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [totalDur - fadeDuration, totalDur], [1, 0], {
    easing: Easing.ease,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

export const MixtapeDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{background: '#0d0d1a'}}>
      <Sequence from={START.title} durationInFrames={DUR.title + FADE}>
        <TitleScene totalFrames={DUR.title} />
      </Sequence>

      <Sequence from={START.upload} durationInFrames={DUR.upload + FADE}>
        <UploadScene totalFrames={DUR.upload} />
      </Sequence>

      <Sequence from={START.mixtape} durationInFrames={DUR.mixtape + FADE}>
        <MixtapeScene totalFrames={DUR.mixtape} />
      </Sequence>

      <Sequence from={START.description} durationInFrames={DUR.description + FADE}>
        <DescriptionScene totalFrames={DUR.description} />
      </Sequence>

      <Sequence from={START.video} durationInFrames={DUR.video + FADE}>
        <VideoScene totalFrames={DUR.video} />
      </Sequence>

      <Sequence from={START.outro} durationInFrames={DUR.outro}>
        <OutroScene totalFrames={DUR.outro} />
      </Sequence>
    </AbsoluteFill>
  );
};
