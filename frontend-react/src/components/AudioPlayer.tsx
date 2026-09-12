import { useRef, useState, useEffect, useCallback } from 'react';
import { Play, Pause, Volume2 } from 'lucide-react';
import type { Boundary } from '../types';

interface Props {
  src: string;
  boundaries?: Boundary[] | null;
}

function fmtMs(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  if (m < 60) return `${m}:${sec.toString().padStart(2, '0')}`;
  const h = Math.floor(m / 60);
  return `${h}:${(m % 60).toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

function fmtSec(s: number): string {
  return fmtMs(s * 1000);
}

export function AudioPlayer({ src, boundaries }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const toggle = () => {
    const a = audioRef.current;
    if (!a) return;
    playing ? a.pause() : a.play();
  };

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = progressRef.current?.getBoundingClientRect();
    if (!rect || !audioRef.current || !duration) return;
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    audioRef.current.currentTime = ratio * duration;
  }, [duration]);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onTime = () => setCurrentTime(a.currentTime);
    const onMeta = () => setDuration(a.duration);
    a.addEventListener('play', onPlay);
    a.addEventListener('pause', onPause);
    a.addEventListener('timeupdate', onTime);
    a.addEventListener('loadedmetadata', onMeta);
    return () => {
      a.removeEventListener('play', onPlay);
      a.removeEventListener('pause', onPause);
      a.removeEventListener('timeupdate', onTime);
      a.removeEventListener('loadedmetadata', onMeta);
    };
  }, []);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="bg-zinc-800/60 rounded-2xl p-4 space-y-3">
      <audio ref={audioRef} src={src} preload="metadata" />

      {/* Controls row */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          aria-label={playing ? 'Pause' : 'Play'}
          className="w-10 h-10 rounded-full bg-violet-600 hover:bg-violet-500 flex items-center justify-center text-white transition-colors flex-shrink-0"
        >
          {playing ? <Pause size={16} fill="white" /> : <Play size={16} fill="white" className="ml-0.5" />}
        </button>

        {/* Progress bar */}
        <div
          ref={progressRef}
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          onClick={seek}
          className="flex-1 h-2 bg-zinc-700 rounded-full cursor-pointer group relative"
        >
          <div
            className="h-full bg-gradient-to-r from-violet-600 to-violet-400 rounded-full relative transition-all"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-white shadow-md opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>

          {/* Track boundary markers */}
          {boundaries && duration > 0 && boundaries.slice(1).map((b) => {
            const pct = (b.start_ms / 1000 / duration) * 100;
            return (
              <div
                key={b.name}
                title={`${b.name} — ${fmtMs(b.start_ms)}`}
                className="absolute top-1/2 -translate-y-1/2 w-1 h-3 bg-amber-400/80 rounded-full"
                style={{ left: `${pct}%` }}
              />
            );
          })}
        </div>

        {/* Time */}
        <span className="text-xs tabular-nums text-zinc-400 flex-shrink-0">
          {fmtSec(currentTime)} / {fmtSec(duration)}
        </span>
        <Volume2 size={14} className="text-zinc-600 flex-shrink-0" />
      </div>

      {/* Track boundary pills */}
      {boundaries && boundaries.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {boundaries.map((b) => (
            <button
              key={b.name}
              onClick={() => {
                if (audioRef.current) audioRef.current.currentTime = b.start_ms / 1000;
              }}
              className="badge badge-violet hover:bg-violet-500/25 transition-colors cursor-pointer"
              title={`Jump to ${b.name}`}
            >
              {fmtMs(b.start_ms)} {b.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
