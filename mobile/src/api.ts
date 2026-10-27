import { API_URL } from './config';
import type { Analysis, ExerciseInfo } from './types';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch {}
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function getExercises(): Promise<ExerciseInfo[]> {
  return json(await fetch(`${API_URL}/exercises`));
}

export async function uploadVideo(uri: string, exercise: string): Promise<Analysis> {
  const form = new FormData();
  // React Native's FormData accepts a { uri, name, type } descriptor for files.
  form.append('video', { uri, name: 'exercise.mp4', type: 'video/mp4' } as unknown as Blob);
  form.append('exercise', exercise);
  return json(await fetch(`${API_URL}/analyses`, { method: 'POST', body: form }));
}

export async function getAnalysis(id: string): Promise<Analysis> {
  return json(await fetch(`${API_URL}/analyses/${id}`));
}

/** Polls until the analysis finishes. Throws with a readable message if it fails. */
export async function waitForAnalysis(id: string, signal?: { cancelled: boolean }): Promise<Analysis> {
  for (;;) {
    if (signal?.cancelled) throw new Error('cancelled');
    const a = await getAnalysis(id);
    if (a.status === 'done') return a;
    if (a.status === 'failed') throw new Error(a.error ?? 'Analysis failed');
    await new Promise((r) => setTimeout(r, 1500));
  }
}
