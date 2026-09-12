import type { Step } from '../types';
import { Check } from 'lucide-react';

interface Props {
  current: Step;
}

const STEPS: { id: Step; label: string }[] = [
  { id: 1, label: 'Upload' },
  { id: 2, label: 'Order & Mix' },
  { id: 3, label: 'Review' },
  { id: 4, label: 'Video' },
  { id: 5, label: 'Download' },
];

export function StepBar({ current }: Props) {
  return (
    <nav aria-label="Progress" className="flex items-center gap-0">
      {STEPS.map((step, idx) => {
        const done = step.id < current;
        const active = step.id === current;

        return (
          <div key={step.id} className="flex items-center">
            {/* Node */}
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={[
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300',
                  done
                    ? 'bg-violet-600 text-white'
                    : active
                    ? 'bg-violet-600 text-white ring-4 ring-violet-600/20'
                    : 'bg-zinc-800 text-zinc-500 border border-zinc-700',
                ].join(' ')}
                aria-current={active ? 'step' : undefined}
              >
                {done ? <Check size={14} strokeWidth={2.5} /> : step.id}
              </div>
              <span
                className={[
                  'text-xs font-medium whitespace-nowrap transition-colors duration-300',
                  active ? 'text-violet-400' : done ? 'text-zinc-400' : 'text-zinc-600',
                ].join(' ')}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line (not after last step) */}
            {idx < STEPS.length - 1 && (
              <div
                className={[
                  'h-px w-12 mx-1 mb-5 transition-all duration-500',
                  done ? 'bg-violet-600' : 'bg-zinc-700',
                ].join(' ')}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
