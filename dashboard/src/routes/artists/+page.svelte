<script lang="ts">
  import type { PageData } from './$types';
  import type { Period } from '$lib/types';
  import ArtistCard from '$lib/components/ArtistCard.svelte';
  import PeriodTabs from '$lib/components/PeriodTabs.svelte';

  let { data }: { data: PageData } = $props();
  let period = $state<Period>('short_term');

  const sorted = $derived(
    [...data.artists].sort((a, b) => {
      const ra = a[`rank_${period}` as keyof typeof a] as number | null;
      const rb = b[`rank_${period}` as keyof typeof b] as number | null;
      return (ra ?? 999) - (rb ?? 999);
    })
  );
</script>

<div class="p-8">
  <div class="flex items-center justify-between mb-6 flex-wrap gap-4">
    <div>
      <h1 class="text-3xl font-bold" style="color: var(--text-primary)">Top Artists</h1>
      <p class="text-sm mt-1" style="color: var(--text-muted)">{data.artists.length} artists tracked</p>
    </div>
    <PeriodTabs bind:period />
  </div>

  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {#each sorted as artist}
      <ArtistCard {artist} {period} />
    {/each}
  </div>
</div>
