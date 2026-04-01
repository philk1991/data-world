<script lang="ts">
  import type { Period } from '$lib/types';

  let { period = $bindable<Period>('short_term') } = $props();

  const tabs: { value: Period; label: string }[] = [
    { value: 'short_term',  label: 'Last 4 Weeks' },
    { value: 'medium_term', label: 'Last 6 Months' },
    { value: 'long_term',   label: 'All Time' },
  ];
</script>

<div class="flex gap-1 p-1 rounded-full w-fit" style="background: var(--bg-highlight)">
  {#each tabs as tab}
    <button
      onclick={() => (period = tab.value)}
      class="px-5 py-2 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer"
      style={period === tab.value
        ? 'background: white; color: black;'
        : 'color: var(--text-muted); background: transparent;'}
    >
      {tab.label}
    </button>
  {/each}
</div>
