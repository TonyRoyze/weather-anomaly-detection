import { json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';

interface GitHubRepoResponse {
	html_url: string;
	stargazers_count: number;
}

export const GET: RequestHandler = async ({ url, fetch }) => {
	const owner = url.searchParams.get('owner')?.trim();
	const repo = url.searchParams.get('repo')?.trim();

	if (!owner || !repo) {
		return json({ message: 'Missing owner or repo' }, { status: 400 });
	}

	const response = await fetch(`https://api.github.com/repos/${owner}/${repo}`, {
		headers: {
			Accept: 'application/vnd.github+json'
		}
	});

	if (!response.ok) {
		return json({ message: 'Unable to load GitHub repository metadata' }, { status: 502 });
	}

	const data = (await response.json()) as GitHubRepoResponse;

	return json({
		url: data.html_url,
		stargazersCount: data.stargazers_count
	});
};
