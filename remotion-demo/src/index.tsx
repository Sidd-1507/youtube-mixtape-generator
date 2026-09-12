// src/index.tsx
// Remotion entry point — THIS is the file you pass to the CLI.
// It must call registerRoot() with the composition tree.
import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
