import { useState } from 'react';
import { Download, RefreshCw, CheckCircle } from 'lucide-react';
import { useMixtape } from '../context/MixtapeContext';

export function Step5Download() {
  const { state, dispatch } = useMixtape();
  const [downloadingMp4, setDownloadingMp4] = useState(false);

  const downloadMp4 = async () => {
    if (!state.videoUrl) return;
    setDownloadingMp4(true);
    try {
      const resp = await fetch(state.videoUrl);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mixtape.mp4';
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingMp4(false);
    }
  };

  const downloadDesc = () => {
    if (!state.descriptionText) return;
    const blob = new Blob([state.descriptionText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'youtube_description.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const durationSec = Math.floor(state.durationMs / 1000);
  const durationFmt = `${Math.floor(durationSec / 60)}:${(durationSec % 60).toString().padStart(2, '0')}`;

  return (
    <div className="max-w-xl mx-auto space-y-6">
      {/* Success banner */}
      <div className="text-center space-y-3">
        <CheckCircle size={48} className="text-green-400 mx-auto" strokeWidth={1.5} />
        <h1 className="text-3xl font-bold tracking-tight">Your Mixtape is Ready!</h1>
        <p className="text-zinc-400">
          {state.uploadedFiles.length} tracks · {durationFmt} total
          {state.sessionId && (
            <> · <span className="font-mono text-xs text-zinc-600">{state.sessionId.slice(0, 8)}…</span></>
          )}
        </p>
      </div>

      {/* Video preview */}
      {state.videoUrl && (
        <div className="card overflow-hidden">
          <video
            src={state.videoUrl}
            controls
            className="w-full aspect-video bg-black"
            aria-label="Mixtape video preview"
          />
        </div>
      )}

      {/* Download buttons */}
      <div className="card p-5 space-y-3">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Download</h2>

        <button
          onClick={downloadMp4}
          disabled={downloadingMp4 || !state.videoUrl}
          className="btn-primary w-full py-3 text-base"
        >
          {downloadingMp4 ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Downloading…
            </>
          ) : (
            <>
              <Download size={18} />
              Download MP4 Video
            </>
          )}
        </button>

        {state.descriptionText && (
          <button onClick={downloadDesc} className="btn-outline w-full py-3">
            <Download size={16} />
            Download Description (.txt)
          </button>
        )}
      </div>

      {/* Description preview */}
      {state.descriptionText && (
        <div className="card p-5 space-y-3">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            YouTube Description
          </h2>
          <pre className="text-sm text-zinc-300 font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto bg-zinc-800/40 rounded-xl p-3">
            {state.descriptionText}
          </pre>
        </div>
      )}

      {/* Next steps */}
      <div className="bg-violet-500/8 border border-violet-500/20 rounded-2xl p-4 space-y-2">
        <p className="text-sm font-semibold text-violet-300">🚀 Next steps</p>
        <ol className="text-sm text-zinc-400 space-y-1.5 list-decimal list-inside">
          <li>Go to <span className="text-zinc-200">studio.youtube.com</span> and click Upload</li>
          <li>Upload the <span className="text-zinc-200">mixtape.mp4</span> file</li>
          <li>Paste the description text with the clickable timestamps</li>
          <li>Publish and share your mixtape 🎵</li>
        </ol>
      </div>

      {/* Start over */}
      <div className="text-center pt-2">
        <button
          onClick={() => dispatch({ type: 'RESET' })}
          className="btn-ghost gap-2 text-zinc-500"
        >
          <RefreshCw size={14} />
          Start Over (New Mixtape)
        </button>
      </div>
    </div>
  );
}
