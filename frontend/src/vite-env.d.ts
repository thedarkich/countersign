/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'mock' | 'live'
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
