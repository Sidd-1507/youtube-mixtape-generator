import { useState } from 'react';
import { Film, Image as ImageIcon, AlertCircle } from 'lucide-react';
import { useMixtape } from '../context/MixtapeContext';
import { createVideo, resolveUrl } from '../api/client';
import { Dropzone } from '../components/Dropzone';

export function Step4Video() {
  const { state, dispatch, goTo } = useMixtape();
  const [bgImage, setBgImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const handleImage = (files: File[]) => {
    const f = files[0];
    if (!f) return;
    setBgImage(f);
    // Local preview via object URL
    const url = URL.createObjectURL(f);
    setPreview(url);
  };

  const handleGenerate = async () => {
    if (!state.sessionId || !bgImage) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const resp = await createVideo(state.sessionId, bgImage);
      dispatch({ type: 'VIDEO_SUCCESS', payload: resolveUrl(resp.video_url) });
      goTo(5);
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Create Video</h1>
        <p className="text-zinc-400">
          Add a background image to render your mixtape as an MP4 for YouTube.
        </p>
      </div>

      <div className="card p-5 space-y-5">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
          Background Image
        </h2>

        {preview ? (
          <div className="relative rounded-xl overflow-hidden aspect-video bg-zinc-800">
            <img src={preview} alt="Background preview" className="w-full h-full object-cover" />
            <button
              onClick={() => { setBgImage(null); setPreview(null); }}
              className="absolute top-3 right-3 bg-black/60 hover:bg-black/80 text-white rounded-lg px-3 py-1.5 text-xs transition-colors"
            >
              Change
            </button>
          </div>
        ) : (
          <Dropzone
            onFiles={handleImage}
            accept=".jpg,.jpeg,.png"
            multiple={false}
            icon={<ImageIcon size={22} />}
            title="Drop your background image"
            subtitle="or click to browse"
            hint="JPEG or PNG · 1920×1080 recommended for YouTube"
          />
        )}

        <div className="bg-zinc-800/40 rounded-xl p-3 text-xs text-zinc-500 border border-zinc-800">
          <p className="font-medium text-zinc-400 mb-1">💡 What happens next:</p>
          <p>ffmpeg will loop your image for the full duration of the audio and encode it as an H.264 MP4 — the format YouTube prefers. This may take 30–120 seconds.</p>
        </div>

        {state.error && (
          <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
            <AlertCircle size={16} className="flex-shrink-0" />
            {state.error}
          </div>
        )}

        <button
          className="btn-primary w-full py-3"
          onClick={handleGenerate}
          disabled={!bgImage || state.loading}
        >
          {state.loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Encoding video… this may take a minute
            </>
          ) : (
            <>
              <Film size={16} />
              Generate MP4 Video
            </>
          )}
        </button>
      </div>

      <div className="flex justify-between">
        <button className="btn-ghost" onClick={() => goTo(3)}>← Back</button>
      </div>
    </div>
  );
}
