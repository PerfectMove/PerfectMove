// Address of the PerfectMove backend. Set EXPO_PUBLIC_API_URL (e.g. in mobile/.env)
// to your Hugging Face Space, https://<user>-perfectmove.hf.space, or for local
// development to your computer's LAN address (http://192.168.1.20:8000), not localhost.
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
