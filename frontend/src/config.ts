// Set VITE_API_URL in frontend/.env.local (see .env.example) when the API isn't on localhost.
export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";
