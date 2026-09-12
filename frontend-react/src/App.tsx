import { Music } from 'lucide-react';
import { MixtapeProvider, useMixtape } from './context/MixtapeContext';
import { StepBar } from './components/StepBar';
import { Step1Upload } from './steps/Step1Upload';
import { Step2Order } from './steps/Step2Order';
import { Step3Review } from './steps/Step3Review';
import { Step4Video } from './steps/Step4Video';
import { Step5Download } from './steps/Step5Download';

function Shell() {
  const { state } = useMixtape();

  const STEPS = {
    1: <Step1Upload />,
    2: <Step2Order />,
    3: <Step3Review />,
    4: <Step4Video />,
    5: <Step5Download />,
  } as const;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="sticky top-0 z-10 bg-zinc-950/80 backdrop-blur border-b border-zinc-900">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center">
              <Music size={16} className="text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight">Mixtape</span>
            <span className="hidden sm:inline text-xs text-zinc-600 font-normal ml-1">
              YouTube Generator
            </span>
          </div>

          {/* Step indicator — centered */}
          <div className="absolute left-1/2 -translate-x-1/2">
            <StepBar current={state.step} />
          </div>

          {/* Session info (right) */}
          {state.sessionId && (
            <div className="hidden lg:flex items-center gap-2 text-xs text-zinc-600">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-dot" />
              Session active
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-12">
        {STEPS[state.step]}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-900 py-6 px-6 text-center">
        <p className="text-xs text-zinc-700">
          FastAPI · pydub · ffmpeg ·{' '}
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="text-zinc-600 hover:text-zinc-400 transition-colors underline underline-offset-2"
          >
            API Docs
          </a>
        </p>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <MixtapeProvider>
      <Shell />
    </MixtapeProvider>
  );
}
