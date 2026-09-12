import { useState } from 'react';
import { Copy, Download, Check, AlertCircle, RefreshCw } from 'lucide-react';
import { useMixtape } from '../context/MixtapeContext';
import { generateDescription } from '../api/client';
import { AudioPlayer } from '../components/AudioPlayer';

export function Step3Review() {
  const { state, dispatch, goTo } = useMixtape();
  const [copied, setCopied] = useState(false);
  const [localDesc, setLocalDesc] = useState<string | null>(state.descriptionText);

  const fetchDesc = async () => {
    if (!state.sessionId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const resp = await generateDescription(
        state.sessionId,
        '🎵 Mixtape Tracklist\n',
        '\n\n#mixtape #music',
      );
      dispatch({ type: 'DESCRIPTION_SUCCESS', payload: resp.description });
      setLocalDesc(resp.description);
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  };

  const copyDesc = async () => {
    if (!localDesc) return;
    await navigator.clipboard.writeText(localDesc);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadDesc = () => {
    if (!localDesc) return;
    const blob = new Blob([localDesc], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'youtube_description.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Review Your Mixtape</h1>
        <p className="text-zinc-400">Listen to the merged audio and generate your YouTube description.</p>
      </div>

      {/* Audio player */}
      <div className="card p-5 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
          Merged Audio Preview
        </h2>
        {state.mixtapeAudioUrl && (
          <AudioPlayer src={state.mixtapeAudioUrl} boundaries={state.boundaries} />
        )}

        {/* Boundary list */}
        {state.boundaries && (
          <div className="divide-y divide-zinc-800">
            {state.boundaries.map((b, idx) => {
              const s = Math.floor(b.start_ms / 1000);
              const m = Math.floor(s / 60);
              const sec = s % 60;
              const ts = `${m}:${sec.toString().padStart(2, '0')}`;
              return (
                <div key={b.name} className="flex items-center gap-3 py-2">
                  <span className="text-xs text-zinc-600 w-4">{idx + 1}</span>
                  <span className="badge badge-violet tabular-nums">{ts}</span>
                  <span className="flex-1 text-sm text-zinc-300 truncate">{b.name}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Description */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            YouTube Description
          </h2>
          <div className="flex gap-2">
            {localDesc && (
              <>
                <button onClick={copyDesc} className="btn-ghost text-xs py-1.5 px-3">
                  {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
                </button>
                <button onClick={downloadDesc} className="btn-ghost text-xs py-1.5 px-3">
                  <Download size={12} /> .txt
                </button>
              </>
            )}
            <button onClick={fetchDesc} disabled={state.loading} className="btn-outline text-xs py-1.5 px-3">
              {state.loading
                ? <span className="w-3 h-3 border border-zinc-500 border-t-white rounded-full animate-spin" />
                : <><RefreshCw size={12} /> {localDesc ? 'Regenerate' : 'Generate'}</>
              }
            </button>
          </div>
        </div>

        {localDesc ? (
          <textarea
            className="field w-full p-3 text-sm font-mono leading-relaxed resize-none h-48"
            value={localDesc}
            onChange={(e) => setLocalDesc(e.target.value)}
            spellCheck={false}
            aria-label="YouTube description"
          />
        ) : (
          <div className="h-48 rounded-xl bg-zinc-800/40 flex flex-col items-center justify-center gap-2 border border-dashed border-zinc-700">
            <p className="text-sm text-zinc-500">Click "Generate" to create your timestamps</p>
          </div>
        )}
      </div>

      {/* Error */}
      {state.error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
          <AlertCircle size={16} className="flex-shrink-0" />
          {state.error}
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between items-center">
        <button className="btn-ghost" onClick={() => goTo(2)}>← Back</button>
        <button
          className="btn-primary"
          onClick={() => { dispatch({ type: 'DESCRIPTION_SUCCESS', payload: localDesc ?? '' }); goTo(4); }}
          disabled={!localDesc}
        >
          Continue to Video →
        </button>
      </div>
    </div>
  );
}
