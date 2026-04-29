export interface TopArtist {
  artist_id: string;
  artist_name: string;
  genres: string | null;
  popularity: number;
  followers: number;
  image_url: string | null;
  rank_short_term: number | null;
  rank_medium_term: number | null;
  rank_long_term: number | null;
  spotify_url: string;
  ingested_at: string;
}

export interface TopTrack {
  track_id: string;
  track_name: string;
  artist_names: string;
  album_name: string;
  album_release_date: string | null;
  duration_minutes: number;
  explicit: boolean;
  popularity: number;
  rank_short_term: number | null;
  rank_medium_term: number | null;
  rank_long_term: number | null;
  spotify_url: string;
  ingested_at: string;
}

export interface RecentPlay {
  played_at: string;
  played_date: string;
  played_hour: number;
  track_id: string;
  track_name: string;
  artist_names: string;
  album_name: string;
  duration_minutes: number;
  explicit: boolean;
  popularity: number;
  spotify_url: string;
  context_type: string | null;
  ingested_at: string;
}

export type Period = 'short_term' | 'medium_term' | 'long_term';
