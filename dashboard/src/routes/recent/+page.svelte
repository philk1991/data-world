<script lang="ts">
  import type { PageData } from './$types';
  import RecentTrackRow from '$lib/components/RecentTrackRow.svelte';
  import HourlyBarChart from '$lib/components/HourlyBarChart.svelte';

  let { data }: { data: PageData } = $props();
</script>

<div class="p-8 max-w-5xl mx-auto">
  <div class="mb-8">
    <h1 class="text-3xl font-bold" style="color: var(--text-primary)">Recently Played</h1>
    <p class="text-sm mt-1" style="color: var(--text-muted)">Your last {data.plays.length} plays</p>
  </div>

  <!-- Stats -->
  <div class="grid grid-cols-2 gap-4 mb-8">
    {#each [
      { label: 'Total Plays', value: data.totalPlays },
      { label: 'Unique Tracks', value: data.uniqueTracks },
    ] as stat}
      <div class="rounded-xl p-5" style="background: var(--bg-elevated)">
        <p class="text-3xl font-bold" style="color: var(--accent-green)">{stat.value}</p>
        <p class="text-sm mt-1" style="color: var(--text-muted)">{stat.label}</p>
      </div>
    {/each}
  </div>

  <!-- Hourly chart -->
  <div class="rounded-xl p-6 mb-8" style="background: var(--bg-elevated)">
    <h2 class="font-semibold mb-4" style="color: var(--text-primary)">Listening by Hour</h2>
    <HourlyBarChart data={data.byHour} />
  </div>

  <!-- Play feed -->
  <div class="rounded-xl p-6" style="background: var(--bg-elevated)">
    <h2 class="font-semibold mb-4" style="color: var(--text-primary)">Play History</h2>
    {#each data.plays as play}
      <RecentTrackRow {play} />
    {/each}
  </div>
</div>
