import { query } from '$lib/server/db';
import type { RecentPlay } from '$lib/types';

export const load = async () => {
  const plays = await query<RecentPlay>(
    'SELECT * FROM stg_recently_played ORDER BY played_at DESC LIMIT 50'
  );

  // Aggregate plays by hour for chart
  const byHour = Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    count: plays.filter((p) => p.played_hour === h).length,
  }));

  const totalPlays = plays.length;
  const uniqueTracks = new Set(plays.map((p) => p.track_id)).size;

  return { plays, byHour, totalPlays, uniqueTracks };
};
