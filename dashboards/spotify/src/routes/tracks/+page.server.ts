import { query } from '$lib/server/db';
import type { TopTrack } from '$lib/types';

export const load = async () => {
  const tracks = await query<TopTrack>(
    'SELECT * FROM top_tracks_by_period ORDER BY COALESCE(rank_short_term, 999)'
  );
  return { tracks };
};
