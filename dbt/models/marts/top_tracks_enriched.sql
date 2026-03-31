-- Top tracks joined with audio features for rich analysis
with tracks as (
    select * from {{ ref('top_tracks_by_period') }}
),

features as (
    select * from {{ ref('stg_audio_features') }}
)

select
    t.track_id,
    t.track_name,
    t.artist_names,
    t.album_name,
    t.album_release_date,
    t.duration_minutes,
    t.explicit,
    t.popularity,
    t.rank_short_term,
    t.rank_medium_term,
    t.rank_long_term,

    -- Audio features
    f.danceability,
    f.energy,
    f.valence,
    f.tempo,
    f.acousticness,
    f.instrumentalness,
    f.speechiness,
    f.liveness,
    f.loudness,
    f.key,
    f.mode,
    f.time_signature,

    t.spotify_url
from tracks t
left join features f using (track_id)
order by coalesce(t.rank_short_term, 999)
