import { query } from '$lib/server/db';
import type { TopArtist } from '$lib/types';

export const load = async () => {
  const artists = await query<TopArtist>(
    'SELECT * FROM top_artists_by_period ORDER BY COALESCE(rank_short_term, 999)'
  );
  return { artists };
};
