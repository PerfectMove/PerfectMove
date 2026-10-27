export type CheckStatus = 'pass' | 'warn' | 'fail';

export interface Check {
  id: string;
  title: string;
  status: CheckStatus;
  detail: string;
  tip: string | null;
  reps_affected: number[];
}

export interface Rep {
  number: number;
  start_s: number;
  bottom_s: number;
  end_s: number;
  metrics: Record<string, number>;
}

export interface ExerciseReport {
  exercise: string;
  camera_view: 'side' | 'front';
  rep_count: number;
  score: number;
  checks: Check[];
  reps: Rep[];
  notes: string[];
}

export interface AnalysisResult {
  report: ExerciseReport;
  feedback: string;
  feedback_source: 'claude' | 'rules';
}

export interface Analysis {
  id: string;
  exercise: string;
  status: 'processing' | 'done' | 'failed';
  result: AnalysisResult | null;
  error: string | null;
}

export interface ExerciseInfo {
  id: string;
  name: string;
  filming_tips: string[];
}
