/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend API base URL, e.g. http://localhost:8000/api. Public: never put secrets in VITE_*. */
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
