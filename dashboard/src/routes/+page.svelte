<script lang="ts">
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const heroArtist = $derived(data.heroArtist);
  const heroTrack = $derived(data.heroTrack);

  const formattedDate = $derived(data.lastIngested
    ? new Date(data.lastIngested).toLocaleString('en-GB', {
        day: 'numeric', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit'
      })
    : 'Never');
</script>

<div class="p-8 max-w-5xl mx-auto">
  <!-- Header -->
  <div class="mb-8">
    <h1 class="text-3xl font-bold" style="color: var(--text-primary)">Overview</h1>
    <p class="text-sm mt-1" style="color: var(--text-muted)">Last updated: {formattedDate}</p>
  </div>

  <!-- Hero cards -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
    <!-- Hero artist -->
    {#if heroArtist}
      <div class="rounded-xl overflow-hidden relative group" style="background: var(--bg-elevated)">
        {#if heroArtist.image_url}
          <img src={heroArtist.image_url} alt={heroArtist.artist_name}
            class="w-full h-48 object-cover opacity-60 group-hover:opacity-70 transition-opacity" />
        {:else}
          <div class="w-full h-48 flex items-center justify-center text-6xl font-bold"
            style="background: var(--bg-highlight); color: var(--accent-green)">
            {heroArtist.artist_name[0]}
          </div>
        {/if}
        <div class="absolute inset-0 flex flex-col justify-end p-5"
          style="background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 60%)">
          <span class="text-xs font-semibold uppercase tracking-widest mb-1"
            style="color: var(--accent-green)">Your #1 Artist Right Now</span>
          <h2 class="text-2xl font-bold" style="color: var(--text-primary)">{heroArtist.artist_name}</h2>
          {#if heroArtist.genres}
            <p class="text-sm mt-1 capitalize" style="color: var(--text-muted)">
              {heroArtist.genres.split(', ').slice(0, 2).join(' · ')}
            </p>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Hero track -->
    {#if heroTrack}
      <div class="rounded-xl p-6 flex flex-col justify-between" style="background: var(--bg-elevated)">
        <div>
          <span class="text-xs font-semibold uppercase tracking-widest"
            style="color: var(--accent-green)">Your #1 Track Right Now</span>
          <h2 class="text-2xl font-bold mt-2 leading-tight" style="color: var(--text-primary)">
            {heroTrack.track_name}
          </h2>
          <p class="text-base mt-1" style="color: var(--text-muted)">{heroTrack.artist_names}</p>
          <p class="text-sm mt-1" style="color: var(--text-subdued)">{heroTrack.album_name}</p>
        </div>
        <div class="flex items-center gap-4 mt-6">
          <a
            href={heroTrack.spotify_url}
            target="_blank"
            rel="noopener noreferrer"
            class="px-4 py-2 rounded-full text-sm font-semibold transition-colors"
            style="background: var(--accent-green); color: #000"
          >
            Open in Spotify
          </a>
          {#if heroTrack.explicit}
            <span class="text-xs font-bold px-1.5 py-0.5 rounded border"
              style="border-color: var(--text-subdued); color: var(--text-subdued)">E</span>
          {/if}
          <span class="text-sm" style="color: var(--text-muted)">
            {Math.floor(heroTrack.duration_minutes)}:{Math.round((heroTrack.duration_minutes % 1) * 60).toString().padStart(2,'0')}
          </span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Nav tiles -->
  <h2 class="text-lg font-semibold mb-4" style="color: var(--text-primary)">Explore</h2>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    {#each [
      { href: '/artists', label: 'Top Artists', desc: 'Your most-played artists across all time periods', icon: '🎤' },
      { href: '/tracks',  label: 'Top Tracks',  desc: 'Your most-played songs ranked by period', icon: '🎵' },
      { href: '/recent',  label: 'Recently Played', desc: 'Your listening history and activity patterns', icon: '🕐' },
    ] as tile}
      <a
        href={tile.href}
        class="rounded-xl p-5 flex flex-col gap-2 transition-colors hover:opacity-90"
        style="background: var(--bg-elevated)"
      >
        <span class="text-2xl">{tile.icon}</span>
        <span class="font-semibold text-sm" style="color: var(--text-primary)">{tile.label}</span>
        <span class="text-xs leading-relaxed" style="color: var(--text-muted)">{tile.desc}</span>
      </a>
    {/each}
  </div>
</div>
