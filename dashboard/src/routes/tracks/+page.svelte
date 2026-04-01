<script lang="ts">
  import type { PageData } from './$types';
  import type { Period } from '$lib/types';
  import TrackRow from '$lib/components/TrackRow.svelte';
  import PeriodTabs from '$lib/components/PeriodTabs.svelte';

  let { data }: { data: PageData } = $props();
  let period = $state<Period>('short_term');

  const sorted = $derived(
    [...data.tracks].sort((a, b) => {
      const ra = a[`rank_${period}` as keyof typeof a] as number | null;
      const rb = b[`rank_${period}` as keyof typeof b] as number | null;
      return (ra ?? 999) - (rb ?? 999);
    })
  );
</script>

<div class="p-8">
  <div class="flex items-center justify-between mb-6 flex-wrap gap-4">
    <div>
      <h1 class="text-3xl font-bold" style="color: var(--text-primary)">Top Tracks</h1>
      <p class="text-sm mt-1" style="color: var(--text-muted)">{data.tracks.length} tracks tracked</p>
    </div>
    <PeriodTabs bind:period />
  </div>

  <!-- Table header -->
  <div class="flex items-center gap-4 px-4 pb-3 border-b text-xs font-medium uppercase tracking-wider"
    style="border-color: var(--border); color: var(--text-subdued)">
    <div class="w-12 text-center">Rank</div>
    <div class="flex-1">Title</div>
    <div class="hidden md:block w-48">Album</div>
    <div class="w-24 text-right">Duration</div>
    <div class="hidden lg:block w-28">Popularity</div>
  </div>

  <div class="mt-1">
    {#each sorted as track, i}
      <TrackRow {track} {period} index={i} />
    {/each}
  </div>
</div>
