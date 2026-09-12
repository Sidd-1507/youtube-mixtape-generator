import { useRef } from 'react';
import { GripVertical, ChevronUp, ChevronDown, Zap, AlertCircle } from 'lucide-react';
import { useMixtape } from '../context/MixtapeContext';
import { createMixtape } from '../api/client';
import { resolveUrl } from '../api/client';

export function Step2Order() {
  const { state, dispatch, goTo } = useMixtape();
  const { trackOrder, crossfadeMs, normalize } = state;
  const dragSrc = useRef<number | null>(null);

  // ── Reorder helpers ────────────────────────────────────────────────────────

  const move = (from: number, to: number) => {
    if (to < 0 || to >= trackOrder.length) return;
    const next = [...trackOrder];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    dispatch({ type: 'SET_TRACK_ORDER', payload: next });
  };

  const onDragStart = (e: React.DragEvent, idx: number) => {
    dragSrc.current = idx;
    e.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; };

  const onDrop = (e: React.DragEvent, targetIdx: number) => {
    e.preventDefault();
    if (dragSrc.current !== null && dragSrc.current !== targetIdx) {
      move(dragSrc.current, targetIdx);
      dragSrc.current = null;
    }
  };

  // ── Merge action ───────────────────────────────────────────────────────────

  const handleMerge = async () => {
    if (!state.sessionId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const resp = await createMixtape(state.sessionId, trackOrder, crossfadeMs, normalize);
      const audioUrl = resolveUrl(resp.merged_audio_url);
      dispatch({ type: 'MIXTAPE_SUCCESS', payload: { resp, audioUrl } });
      goTo(3);
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  };

  const crossfadeSec = (crossfadeMs / 1000).toFixed(1);

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Order & Mix</h1>
        <p className="text-zinc-400">Drag tracks to reorder, then set crossfade duration.</p>
      </div>

      {/* Track list */}
      <div className="card p-4 space-y-2">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider px-1 pb-1">
          Track Order — drag to rearrange
        </p>

        {trackOrder.map((name, idx) => (
          <div
            key={name}
            draggable
            onDragStart={(e) => onDragStart(e, idx)}
            onDragOver={onDragOver}
            onDrop={(e) => onDrop(e, idx)}
            className="track-row cursor-grab active:cursor-grabbing active:opacity-60 active:scale-[0.98] transition-all"
          >
            <GripVertical size={16} className="text-zinc-600 flex-shrink-0" />
            <span className="badge badge-violet w-6 h-6 justify-center">{idx + 1}</span>
            <span className="flex-1 text-sm font-medium text-zinc-200 truncate">{name}</span>
            <div className="flex gap-1">
              <button
                onClick={() => move(idx, idx - 1)}
                disabled={idx === 0}
                aria-label="Move up"
                className="p-1 rounded text-zinc-600 hover:text-zinc-300 disabled:opacity-20 transition-colors"
              >
                <ChevronUp size={14} />
              </button>
              <button
                onClick={() => move(idx, idx + 1)}
                disabled={idx === trackOrder.length - 1}
                aria-label="Move down"
                className="p-1 rounded text-zinc-600 hover:text-zinc-300 disabled:opacity-20 transition-colors"
              >
                <ChevronDown size={14} />
              </button>
            </div>
          </div>
        ))}

        {/* Crossfade visualiser — a thin line between tracks */}
        <p className="text-xs text-zinc-600 px-1 pt-2 flex items-center gap-1">
          <Zap size={11} className="text-violet-500" />
          Each track overlaps the next by <span className="text-violet-400 font-medium">{crossfadeSec}s</span>
        </p>
      </div>

      {/* Crossfade slider */}
      <div className="card p-4 space-y-4">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-zinc-200" htmlFor="crossfade-slider">
            Crossfade Duration
          </label>
          <span className="badge badge-violet">{crossfadeMs} ms</span>
        </div>

        <input
          id="crossfade-slider"
          type="range"
          min={0}
          max={5000}
          step={100}
          value={crossfadeMs}
          onChange={(e) => dispatch({ type: 'SET_CROSSFADE', payload: Number(e.target.value) })}
          className="w-full accent-violet-500 cursor-pointer"
          aria-valuetext={`${crossfadeSec} seconds`}
        />

        <div className="flex justify-between text-xs text-zinc-600">
          <span>0ms — Hard cut</span>
          <span>5000ms — 5s blend</span>
        </div>

        {/* Normalize toggle */}
        <label className="flex items-center gap-3 cursor-pointer select-none group">
          <div
            role="switch"
            aria-checked={normalize}
            tabIndex={0}
            onClick={() => dispatch({ type: 'SET_NORMALIZE', payload: !normalize })}
            onKeyDown={(e) => e.key === 'Enter' && dispatch({ type: 'SET_NORMALIZE', payload: !normalize })}
            className={[
              'relative w-10 h-5.5 rounded-full transition-colors duration-200 flex-shrink-0',
              normalize ? 'bg-violet-600' : 'bg-zinc-700',
            ].join(' ')}
          >
            <div className={[
              'absolute top-0.5 w-4.5 h-4.5 rounded-full bg-white shadow transition-transform duration-200',
              normalize ? 'translate-x-5' : 'translate-x-0.5',
            ].join(' ')} />
          </div>
          <div>
            <p className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
              Normalize volume
            </p>
            <p className="text-xs text-zinc-500">Equalizes loudness to −14 dBFS across all tracks</p>
          </div>
        </label>
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
        <button className="btn-ghost" onClick={() => goTo(1)}>← Back</button>
        <button className="btn-primary" onClick={handleMerge} disabled={state.loading}>
          {state.loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Merging tracks…
            </>
          ) : (
            'Generate Mixtape →'
          )}
        </button>
      </div>

      {state.loading && (
        <p className="text-center text-xs text-zinc-500">
          This may take 10–30 seconds depending on file sizes…
        </p>
      )}
    </div>
  );
}
