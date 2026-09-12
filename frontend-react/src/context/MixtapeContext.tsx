import React, { createContext, useContext, useReducer } from 'react';
import type { MixtapeState, Action, Step } from '../types';

// ─── Initial state ────────────────────────────────────────────────────────────

const initial: MixtapeState = {
  step: 1,
  sessionId: null,
  uploadedFiles: [],
  trackOrder: [],
  crossfadeMs: 2000,
  normalize: true,
  mixtapeReady: false,
  mixtapeAudioUrl: null,
  durationMs: 0,
  boundaries: null,
  descriptionText: null,
  videoReady: false,
  videoUrl: null,
  loading: false,
  error: null,
};

// ─── Reducer ──────────────────────────────────────────────────────────────────

function reducer(state: MixtapeState, action: Action): MixtapeState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, loading: action.payload, error: action.payload ? null : state.error };

    case 'SET_ERROR':
      return { ...state, error: action.payload, loading: false };

    case 'UPLOAD_SUCCESS':
      return {
        ...state,
        loading: false,
        error: null,
        sessionId: action.payload.session_id,
        uploadedFiles: action.payload.files,
        trackOrder: action.payload.files, // default order = upload order
      };

    case 'GO_TO_STEP':
      return { ...state, step: action.payload };

    case 'SET_TRACK_ORDER':
      return { ...state, trackOrder: action.payload };

    case 'SET_CROSSFADE':
      return { ...state, crossfadeMs: action.payload };

    case 'SET_NORMALIZE':
      return { ...state, normalize: action.payload };

    case 'MIXTAPE_SUCCESS':
      return {
        ...state,
        loading: false,
        error: null,
        mixtapeReady: true,
        mixtapeAudioUrl: action.payload.audioUrl,
        durationMs: action.payload.resp.duration_ms,
        boundaries: action.payload.resp.boundaries,
      };

    case 'DESCRIPTION_SUCCESS':
      return { ...state, loading: false, error: null, descriptionText: action.payload };

    case 'VIDEO_SUCCESS':
      return { ...state, loading: false, error: null, videoReady: true, videoUrl: action.payload };

    case 'RESET':
      return { ...initial };

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────────────────

interface ContextValue {
  state: MixtapeState;
  dispatch: React.Dispatch<Action>;
  goTo: (step: Step) => void;
}

const MixtapeContext = createContext<ContextValue | null>(null);

export function MixtapeProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initial);

  const goTo = (step: Step) => dispatch({ type: 'GO_TO_STEP', payload: step });

  return (
    <MixtapeContext.Provider value={{ state, dispatch, goTo }}>
      {children}
    </MixtapeContext.Provider>
  );
}

export function useMixtape(): ContextValue {
  const ctx = useContext(MixtapeContext);
  if (!ctx) throw new Error('useMixtape must be used inside MixtapeProvider');
  return ctx;
}
