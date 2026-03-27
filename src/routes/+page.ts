import { redirect } from '@sveltejs/kit';

const isTauriBuild = import.meta.env.VITE_TAURI_BUILD === '1';

export const load = () => {
	if (isTauriBuild) {
		throw redirect(307, '/dashboard');
	}
};

