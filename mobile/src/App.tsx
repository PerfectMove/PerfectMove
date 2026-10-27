import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, View,
} from 'react-native';
import { getExercises, uploadVideo, waitForAnalysis } from './api';
import type { Analysis, Check, CheckStatus, ExerciseInfo } from './types';

const COLORS: Record<CheckStatus, string> = { pass: '#1a9a52', warn: '#d98a00', fail: '#d33a3a' };
const ICONS: Record<CheckStatus, string> = { pass: '✓', warn: '!', fail: '✕' };

type Phase =
  | { name: 'home' }
  | { name: 'analyzing' }
  | { name: 'result'; analysis: Analysis }
  | { name: 'error'; message: string };

export default function App() {
  const [exercises, setExercises] = useState<ExerciseInfo[]>([]);
  const [exercise, setExercise] = useState<ExerciseInfo | null>(null);
  const [phase, setPhase] = useState<Phase>({ name: 'home' });
  const [loadError, setLoadError] = useState<string | null>(null);
  const run = useRef({ cancelled: false });

  useEffect(() => {
    getExercises()
      .then((list) => {
        setExercises(list);
        setExercise(list[0] ?? null);
      })
      .catch((e: Error) => setLoadError(`Can't reach the server: ${e.message}`));
    return () => { run.current.cancelled = true; };
  }, []);

  async function analyze(source: 'camera' | 'library') {
    if (!exercise) return;
    const options: ImagePicker.ImagePickerOptions = {
      mediaTypes: ['videos'],
      videoMaxDuration: 90,
    };
    let picked: ImagePicker.ImagePickerResult;
    if (source === 'camera') {
      const perm = await ImagePicker.requestCameraPermissionsAsync();
      if (!perm.granted) {
        setPhase({ name: 'error', message: 'Camera permission is needed to record. You can pick a video from your library instead.' });
        return;
      }
      picked = await ImagePicker.launchCameraAsync(options);
    } else {
      picked = await ImagePicker.launchImageLibraryAsync(options);
    }
    if (picked.canceled) return;

    run.current = { cancelled: false };
    setPhase({ name: 'analyzing' });
    try {
      const created = await uploadVideo(picked.assets[0].uri, exercise.id);
      const done = await waitForAnalysis(created.id, run.current);
      setPhase({ name: 'result', analysis: done });
    } catch (e) {
      if (!run.current.cancelled) setPhase({ name: 'error', message: (e as Error).message });
    }
  }

  const home = () => { run.current.cancelled = true; setPhase({ name: 'home' }); };

  return (
    <SafeAreaView style={s.screen}>
      <StatusBar style="auto" />
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.title}>PerfectMove</Text>

        {phase.name === 'home' && (
          <>
            {loadError && <Text style={s.error}>{loadError}</Text>}
            <Text style={s.subtitle}>Record your set and get a form check.</Text>
            {exercise && (
              <View style={s.card}>
                <Text style={s.cardTitle}>{exercise.name}</Text>
                {exercise.filming_tips.map((t) => <Text key={t} style={s.tip}>• {t}</Text>)}
              </View>
            )}
            <Button label="Record a video" onPress={() => analyze('camera')} disabled={!exercise} />
            <Button label="Choose from library" secondary onPress={() => analyze('library')} disabled={!exercise} />
          </>
        )}

        {phase.name === 'analyzing' && (
          <View style={s.center}>
            <ActivityIndicator size="large" />
            <Text style={s.subtitle}>Analyzing your form… this can take up to a minute.</Text>
            <Button label="Cancel" secondary onPress={home} />
          </View>
        )}

        {phase.name === 'error' && (
          <>
            <Text style={s.error}>{phase.message}</Text>
            <Button label="Try again" onPress={home} />
          </>
        )}

        {phase.name === 'result' && phase.analysis.result && <Result analysis={phase.analysis} onDone={home} />}
      </ScrollView>
    </SafeAreaView>
  );
}

function Result({ analysis, onDone }: { analysis: Analysis; onDone: () => void }) {
  const { report, feedback } = analysis.result!;
  const color = report.score >= 80 ? COLORS.pass : report.score >= 60 ? COLORS.warn : COLORS.fail;
  const good = report.checks.filter((c) => c.status === 'pass');
  const bad = report.checks.filter((c) => c.status !== 'pass');
  return (
    <>
      <View style={s.card}>
        <Text style={[s.score, { color }]}>{report.score}</Text>
        <Text style={s.subtitle}>{report.rep_count} rep{report.rep_count === 1 ? '' : 's'} · {report.camera_view} view</Text>
      </View>

      {bad.length > 0 && <Text style={s.section}>To fix</Text>}
      {bad.map((c) => <CheckRow key={c.id} check={c} />)}
      {good.length > 0 && <Text style={s.section}>Done well</Text>}
      {good.map((c) => <CheckRow key={c.id} check={c} />)}

      <Text style={s.section}>Coach's notes</Text>
      <View style={s.card}><Text style={s.body}>{feedback}</Text></View>
      {report.notes.map((n) => <Text key={n} style={s.note}>{n}</Text>)}

      <Button label="Analyze another set" onPress={onDone} />
    </>
  );
}

function CheckRow({ check }: { check: Check }) {
  return (
    <View style={s.card}>
      <View style={s.row}>
        <View style={[s.badge, { backgroundColor: COLORS[check.status] }]}>
          <Text style={s.badgeText}>{ICONS[check.status]}</Text>
        </View>
        <Text style={s.cardTitle}>{check.title}</Text>
      </View>
      <Text style={s.body}>{check.detail}</Text>
      {check.tip && <Text style={s.tipText}>{check.tip}</Text>}
      {check.reps_affected.length > 0 && (
        <Text style={s.note}>Reps affected: {check.reps_affected.join(', ')}</Text>
      )}
    </View>
  );
}

function Button({ label, onPress, secondary, disabled }: {
  label: string; onPress: () => void; secondary?: boolean; disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[s.button, secondary && s.buttonSecondary, disabled && { opacity: 0.5 }]}
    >
      <Text style={[s.buttonText, secondary && { color: '#2457d6' }]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#f5f6f8' },
  content: { padding: 20, gap: 12 },
  center: { alignItems: 'center', gap: 16, paddingTop: 40 },
  title: { fontSize: 32, fontWeight: '800', color: '#111' },
  subtitle: { fontSize: 16, color: '#555', textAlign: 'center' },
  section: { fontSize: 18, fontWeight: '700', marginTop: 8, color: '#111' },
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, gap: 6 },
  cardTitle: { fontSize: 17, fontWeight: '600', color: '#111' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  badge: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  badgeText: { color: '#fff', fontWeight: '800' },
  body: { fontSize: 15, color: '#222', lineHeight: 22 },
  tip: { fontSize: 15, color: '#444', lineHeight: 22 },
  tipText: { fontSize: 15, color: '#2457d6', lineHeight: 22 },
  note: { fontSize: 13, color: '#666' },
  score: { fontSize: 64, fontWeight: '800', textAlign: 'center' },
  error: { color: COLORS.fail, fontSize: 16 },
  button: { backgroundColor: '#2457d6', borderRadius: 12, padding: 16, alignItems: 'center' },
  buttonSecondary: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#2457d6' },
  buttonText: { color: '#fff', fontSize: 17, fontWeight: '600' },
});
