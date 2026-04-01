<script lang="ts">
  let { data }: { data: { hour: number; count: number }[] } = $props();

  const max = $derived(Math.max(...data.map((d) => d.count), 1));

  const labels = ['12a','1a','2a','3a','4a','5a','6a','7a','8a','9a','10a','11a',
                  '12p','1p','2p','3p','4p','5p','6p','7p','8p','9p','10p','11p'];
</script>

<div class="w-full">
  <div class="flex items-end gap-1 h-32">
    {#each data as d}
      <div class="flex-1 flex flex-col items-center gap-1 group">
        <div
          class="w-full rounded-sm transition-all duration-300"
          style="height: {(d.count / max) * 100}%; min-height: 2px; background: {d.count > 0 ? 'var(--accent-green)' : 'var(--bg-highlight)'}"
          title="{labels[d.hour]}: {d.count} plays"
        ></div>
      </div>
    {/each}
  </div>
  <!-- Hour labels — show every 3 hours -->
  <div class="flex gap-1 mt-1">
    {#each data as d}
      <div class="flex-1 text-center">
        {#if d.hour % 6 === 0}
          <span class="text-xs" style="color: var(--text-subdued)">{labels[d.hour]}</span>
        {/if}
      </div>
    {/each}
  </div>
</div>
