import { useState } from 'react';
import { Music, X, AlertCircle } from 'lucide-react';
import { useMixtape } from '../context/MixtapeContext';
import { uploadTracks } from '../api/client';
import { Dropzone } from '../components/Dropzone';

const ALLOWED_EXT = new Set(['.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac']);

function fileExt(name: string): string {
  return name.slice(name.lastIndexOf('.')).toLowerCase();
}

export function Step1Upload() {
  const { state, dispatch, goTo } = useMixtape();
  // Staged files (before upload)
  const [staged, setStaged] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const addFiles = (incoming: File[]) => {
    setValidationError(null);
    const invalid = incoming.filter((f) => !ALLOWED_EXT.has(fileExt(f.name)));
    if (invalid.length) {
      setValidationError(`Unsupported format: ${invalid.map((f) => f.name).join(', ')}`);
      return;
    }
    // Deduplicate by name
    const existing = new Set(staged.map((f) => f.name));
    const newFiles = incoming.filter((f) => !existing.has(f.name));
    setStaged((prev) => [...prev, ...newFiles]);
  };

  const removeStaged = (name: string) => setStaged((prev) => prev.filter((f) => f.name !== name));

  const handleUpload = async () => {
    if (staged.length < 1) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const resp = await uploadTracks(staged);
      dispatch({ type: 'UPLOAD_SUCCESS', payload: resp });
      goTo(2);
    } catch (e) {
      dispatch({ type: 'SET_ERROR', payload: (e as Error).message });
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Upload Your Tracks</h1>
        <p className="text-zinc-400">Drop your audio files to get started. Order them in the next step.</p>
      </div>

      <Dropzone
        onFiles={addFiles}
        accept=".mp3,.wav,.flac,.ogg,.m4a,.aac"
        multiple
        icon={<Music size={24} />}
        title="Drop audio files here"
        subtitle="or click to browse"
        hint="Supports MP3 · WAV · FLAC · OGG · M4A · AAC"
      />

      {/* Validation error */}
      {validationError && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
          <AlertCircle size={16} className="flex-shrink-0" />
          {validationError}
        </div>
      )}

      {/* API error */}
      {state.error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
          <AlertCircle size={16} className="flex-shrink-0" />
          {state.error}
        </div>
      )}

      {/* Staged file list */}
      {staged.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
            {staged.length} file{staged.length !== 1 ? 's' : ''} ready to upload
          </p>
          {staged.map((f, idx) => (
            <div key={f.name} className="track-row">
              <span className="badge badge-violet w-6 h-6 justify-center flex-shrink-0">{idx + 1}</span>
              <Music size={14} className="text-zinc-600 flex-shrink-0" />
              <span className="flex-1 text-sm text-zinc-200 truncate">{f.name}</span>
              <span className="badge badge-zinc">{(f.size / 1024).toFixed(0)} KB</span>
              <button
                onClick={() => removeStaged(f.name)}
                aria-label={`Remove ${f.name}`}
                className="text-zinc-600 hover:text-red-400 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Action row */}
      <div className="flex justify-between items-center pt-2">
        <p className="text-xs text-zinc-600">
          {staged.length < 2 ? 'Add at least 2 tracks to continue' : `${staged.length} tracks ready`}
        </p>
        <button
          className="btn-primary"
          onClick={handleUpload}
          disabled={staged.length < 2 || state.loading}
        >
          {state.loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Uploading…
            </>
          ) : (
            'Continue to Ordering →'
          )}
        </button>
      </div>
    </div>
  );
}
