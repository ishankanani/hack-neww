/// <reference types="vite/client" />
interface ImportMetaEnv { readonly VITE_API_BASE?: string; readonly VITE_GOOGLE_MAPS_API_KEY?: string; readonly VITE_GOOGLE_MAP_ID?: string; readonly VITE_GOOGLE_MAPS_EMBED_API_KEY?: string; }
interface ImportMeta { readonly env: ImportMetaEnv; }
