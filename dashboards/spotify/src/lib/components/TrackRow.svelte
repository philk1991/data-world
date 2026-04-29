<script lang="ts">
  import type { TopTrack, Period } from '$lib/types';
  import RankBadge from './RankBadge.svelte';
  import PopularityBar from './PopularityBar.svelte';

  let { track, period, index }: { track: TopTrack; period: Period; index: number } = $props();

  const rank = $derived(track[`rank_${period}` as keyof TopTrack] as number | null);
  const duration = $derived(() => {
    const mins = Math.floor(track.duration_minutes);
    const secs = Math.round((track.duration_minutes - mins) * 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  });
</script>

<div
  class="flex items-center gap-4 px-4 py-3 rounded-lg transition-colors group"
  style="background: {index % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)'}; opacity: {rank === null ? 0.45 : 1}"
>
  <!-- Rank -->
  <div class="w-12 flex-shrink-0 flex justify-center">
    <RankBadge {rank} />
  </div>

  <!-- Track info -->
  <div class="flex-1 min-w-0">
    <a
      href={track.spotify_url}
      target="_blank"
      rel="noopener noreferrer"
      class="font-medium text-sm truncate block hover:underline"
      style="color: var(--text-primary)"
    >
      {track.track_name}
    </a>
    <p class="text-xs truncate mt-0.5" style="color: var(--text-muted)">
      {track.artist_names}
    </p>
  </div>

  <!-- Album (hidden on small screens) -->
  <div class="hidden md:block w-48 flex-shrink-0">
    <p class="text-xs truncate" style="color: var(--text-muted)">{track.album_name}</p>
  </div>

  <!-- Duration + badges -->
  <div class="flex items-center gap-3 flex-shrink-0">
    {#if track.explicit}
      <span class="text-xs font-bold px-1.5 py-0.5 rounded border text-xs"
        style="border-color: var(--text-subdued); color: var(--text-subdued)">
        E
      </span>
    {/if}
    <span class="text-xs w-10 text-right" style="color: var(--text-muted)">{duration()}</span>
  </div>

  <!-- Popularity -->
  <div class="hidden lg:block w-28 flex-shrink-0">
    <PopularityBar score={track.popularity} />
  </div>
</div>
