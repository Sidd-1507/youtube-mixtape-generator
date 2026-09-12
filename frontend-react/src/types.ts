// ─── Domain types (mirror backend schemas/models.py) ────────────────────────

export interface Boundary {
  name: string;
  start_ms: number;
  end_ms: number;
}

export interface UploadResponse {
  session_id: string;
  files: string[];
  count: number;
}

export interface MixtapeResponse {
  session_id: string;
  merged_audio_url: string;
  duration_ms: number;
  boundaries: Boundary[];
}

export interface DescriptionResponse {
  session_id: string;
  description: string;
}

export interface VideoResponse {
  session_id: string;
  video_url: string;
}

// ─── UI / App state ───────────────────────────────────────────────────────────

export type Step = 1 | 2 | 3 | 4 | 5;

export interface MixtapeState {
  step: Step;
  // Step 1 — Upload
  sessionId: string | null;
  uploadedFiles: string[];
  // Step 2 — Order & Mix
  trackOrder: string[];
  crossfadeMs: number;
  normalize: boolean;
  // Step 3 — Review
  mixtapeReady: boolean;
  mixtapeAudioUrl: string | null;
  durationMs: number;
  boundaries: Boundary[] | null;
  descriptionText: string | null;
  // Step 4 — Video
  videoReady: boolean;
  videoUrl: string | null;
  // Loading / error
  loading: boolean;
  error: string | null;
}

export type Action =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'UPLOAD_SUCCESS'; payload: UploadResponse }
  | { type: 'GO_TO_STEP'; payload: Step }
  | { type: 'SET_TRACK_ORDER'; payload: string[] }
  | { type: 'SET_CROSSFADE'; payload: number }
  | { type: 'SET_NORMALIZE'; payload: boolean }
  | { type: 'MIXTAPE_SUCCESS'; payload: { resp: MixtapeResponse; audioUrl: string } }
  | { type: 'DESCRIPTION_SUCCESS'; payload: string }
  | { type: 'VIDEO_SUCCESS'; payload: string }
  | { type: 'RESET' };
