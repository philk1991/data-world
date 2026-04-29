<script lang="ts">
  let { rank }: { rank: number | null } = $props();
</script>

{#if rank === null}
  <span class="text-xs font-medium px-2 py-0.5 rounded" style="color: var(--text-subdued); background: var(--bg-highlight)">
    —
  </span>
{:else if rank === 1}
  <span class="text-xs font-bold px-2 py-0.5 rounded" style="background: #FFD700; color: #000">
    #1
  </span>
{:else if rank === 2}
  <span class="text-xs font-bold px-2 py-0.5 rounded" style="background: #C0C0C0; color: #000">
    #2
  </span>
{:else if rank === 3}
  <span class="text-xs font-bold px-2 py-0.5 rounded" style="background: #CD7F32; color: #000">
    #3
  </span>
{:else}
  <span class="text-xs font-medium px-2 py-0.5 rounded" style="color: var(--text-muted); background: var(--bg-highlight)">
    #{rank}
  </span>
{/if}
