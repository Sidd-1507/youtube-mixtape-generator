import React, { useRef, useState, useCallback } from 'react';
import { Upload } from 'lucide-react';

interface Props {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  icon?: React.ReactNode;
  title: string;
  subtitle: string;
  hint?: string;
}

export function Dropzone({ onFiles, accept, multiple = true, icon, title, subtitle, hint }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList) return;
      onFiles(Array.from(fileList));
    },
    [onFiles],
  );

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragging(true); };
  const onDragLeave = () => setDragging(false);
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="File upload area"
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      className={[
        'relative flex flex-col items-center justify-center gap-3 p-8 rounded-2xl border-2 border-dashed cursor-pointer',
        'transition-all duration-200 select-none outline-none',
        dragging
          ? 'border-violet-500 bg-violet-500/8 scale-[1.01]'
          : 'border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800/30',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accept}
        multiple={multiple}
        onChange={(e) => handleFiles(e.target.files)}
      />

      <div className={[
        'w-14 h-14 rounded-2xl flex items-center justify-center transition-colors duration-200',
        dragging ? 'bg-violet-500/20 text-violet-400' : 'bg-zinc-800 text-zinc-500',
      ].join(' ')}>
        {icon ?? <Upload size={24} />}
      </div>

      <div className="text-center">
        <p className="font-semibold text-zinc-200">{title}</p>
        <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>
      </div>

      {hint && (
        <p className="text-xs text-zinc-600 border border-zinc-800 rounded-lg px-3 py-1.5 bg-zinc-900/60">
          {hint}
        </p>
      )}
    </div>
  );
}
