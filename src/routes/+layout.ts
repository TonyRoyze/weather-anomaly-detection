const isTauriBuild = import.meta.env.VITE_TAURI_BUILD === '1';

export const prerender = isTauriBuild;
export const ssr = !isTauriBuild;

