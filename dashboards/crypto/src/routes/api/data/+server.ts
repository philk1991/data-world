import { readFileSync } from 'fs';
import { resolve } from 'path';
import type { RequestHandler } from './$types';

const JSON_PATH = resolve(process.cwd(), '../../data/live_data.json');

let cache = '{"prices":[],"trades":[]}';

export const GET: RequestHandler = () => {
	try {
		cache = readFileSync(JSON_PATH, 'utf-8');
	} catch {
		// file not written yet — return last cache
	}
	return new Response(cache, { headers: { 'content-type': 'application/json' } });
};
