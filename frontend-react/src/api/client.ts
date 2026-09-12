// ─── Typed API client — all backend calls go through here. ───────────────────
// No raw fetch() scattered through UI components.
// Every function returns the parsed JSON body or throws with a clear message.

import type { UploadResponse, MixtapeResponse, DescriptionResponse, VideoResponse } from '../types';

const BASE = import.meta.env.VITE_API_URL ?? '';

// Generic fetch wrapper: throws a human-readable Error on non-2xx.
async function apiFetch<T>(path: string, init: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new Error('Cannot reach the backend. Is it running on port 8000?');
  }

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body?.detail ?? detail;
    } catch { /* ignore parse error */ }
    throw new Error(detail);
  }

  return resp.json() as Promise<T>;
}

// ─── Endpoint wrappers ────────────────────────────────────────────────────────

/**
 * POST /upload
 * Sends audio files as multipart/form-data, returns session_id + filenames.
 */
export async function uploadTracks(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  return apiFetch<UploadResponse>('/upload', { method: 'POST', body: form });
}

/**
 * POST /mixtape/create
 * Merges tracks in requested order with given crossfade.
 */
export async function createMixtape(
  sessionId: string,
  order: string[],
  crossfadeMs: number,
  normalize: boolean,
): Promise<MixtapeResponse> {
  return apiFetch<MixtapeResponse>('/mixtape/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, order, crossfade_ms: crossfadeMs, normalize }),
  });
}

/**
 * POST /description/generate
 * Reads saved boundaries and returns a formatted YouTube description.
 */
export async function generateDescription(
  sessionId: string,
  header?: string,
  footer?: string,
): Promise<DescriptionResponse> {
  return apiFetch<DescriptionResponse>('/description/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, header, footer }),
  });
}

/**
 * POST /video/create
 * Sends session_id + background image, triggers ffmpeg, returns video URL.
 */
export async function createVideo(sessionId: string, image: File): Promise<VideoResponse> {
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('image', image);
  return apiFetch<VideoResponse>('/video/create', { method: 'POST', body: form });
}

/**
 * Resolves a relative URL from the API to an absolute URL.
 * e.g. "/storage/abc/merged.mp3"  →  "http://localhost:8000/storage/abc/merged.mp3"
 */
export function resolveUrl(relativeUrl: string): string {
  return `${BASE}${relativeUrl}`;
}
