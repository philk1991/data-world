<script lang="ts">
  import type { TopArtist, Period } from '$lib/types';
  import RankBadge from './RankBadge.svelte';
  import PopularityBar from './PopularityBar.svelte';

  let { artist, period }: { artist: TopArtist; period: Period } = $props();

  const rank = $derived(artist[`rank_${period}` as keyof TopArtist] as number | null);
  const genres = $derived(
    artist.genres ? artist.genres.split(', ').slice(0, 3) : []
  );
  const followers = $derived(
    artist.followers >= 1_000_000
      ? `${(artist.followers / 1_000_000).toFixed(1)}M`
      : artist.followers >= 1_000
        ? `${(artist.followers / 1_000).toFixed(0)}K`
        : artist.followers.toString()
  );
</script>

<div
  class="rounded-lg p-4 flex flex-col gap-3 transition-all duration-200 group"
  style="background: var(--bg-elevated); opacity: {rank === null ? 0.45 : 1}"
>
  <!-- Artist image -->
  <div class="relative aspect-square w-full overflow-hidden rounded-md">
    {#if artist.image_url}
      <img
        src={artist.image_url}
        alt={artist.artist_name}
        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
      />
    {:else}
      <div class="w-full h-full flex items-center justify-center text-4xl font-bold rounded-md"
        style="background: var(--bg-highlight); color: var(--accent-green)">
        {artist.artist_name[0]}
      </div>
    {/if}
    <div class="absolute top-2 left-2">
      <RankBadge {rank} />
    </div>
  </div>

  <!-- Name -->
  <div>
    <a
      href={artist.spotify_url}
      target="_blank"
      rel="noopener noreferrer"
      class="font-semibold text-sm leading-tight hover:underline"
      style="color: var(--text-primary)"
    >
      {artist.artist_name}
    </a>
    {#if rank === null}
      <p class="text-xs mt-0.5" style="color: var(--text-subdued)">Not in top 50</p>
    {/if}
  </div>

  <!-- Genres -->
  {#if genres.length > 0}
    <div class="flex flex-wrap gap-1">
      {#each genres as genre}
        <span class="text-xs px-2 py-0.5 rounded-full capitalize"
          style="background: var(--bg-highlight); color: var(--text-muted)">
          {genre}
        </span>
      {/each}
    </div>
  {/if}

  <!-- Popularity -->
  <PopularityBar score={artist.popularity} />

  <!-- Followers -->
  <p class="text-xs" style="color: var(--text-subdued)">{followers} followers</p>
</div>
