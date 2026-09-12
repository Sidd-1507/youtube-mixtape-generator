// src/Root.tsx
// Remotion entry point — registers the MixtapeDemo composition
import React from 'react';
import {Composition} from 'remotion';
import {MixtapeDemo} from './MixtapeDemo';

const FPS    = 30;
const W      = 1920;
const H      = 1080;

// Scene durations (seconds → frames at 30fps)
export const SCENES = {
  title:       4,   // Scene 1: title card
  upload:      8,   // Scene 2: upload screenshot
  mixtape:    10,   // Scene 3: merged audio player clip
  description: 10,  // Scene 4: description with staggered timestamps
  video:       16,  // Scene 5: video output clip
  outro:        7,  // Scene 6: closing card
} as const;

export const TOTAL_S = Object.values(SCENES).reduce((a, b) => a + b, 0);
// 4+8+10+10+16+7 = 55 seconds

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MixtapeDemo"
        component={MixtapeDemo}
        durationInFrames={TOTAL_S * FPS}
        fps={FPS}
        width={W}
        height={H}
        defaultProps={{}}
      />
    </>
  );
};
