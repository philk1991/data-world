import { query } from '$lib/server/db';
import type { TopArtist, TopTrack } from '$lib/types';

export const load = async () => {
  const [artists, tracks] = await Promise.all([
    query<TopArtist>('SELECT * FROM top_artists_by_period ORDER BY COALESCE(rank_short_term, 999) LIMIT 1'),
    query<TopTrack>('SELECT * FROM top_tracks_by_period ORDER BY COALESCE(rank_short_term, 999) LIMIT 1'),
  ]);

  const ingested = await query<{ ingested_at: string }>(
    'SELECT MAX(ingested_at) AS ingested_at FROM top_artists_by_period'
  );

  return {
    heroArtist: artists[0] ?? null,
    heroTrack: tracks[0] ?? null,
    lastIngested: ingested[0]?.ingested_at ?? null,
  };
};
