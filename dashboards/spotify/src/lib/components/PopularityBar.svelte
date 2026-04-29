<script lang="ts">
  let { score }: { score: number } = $props();
</script>

<div class="flex items-center gap-2">
  <div class="flex-1 h-1 rounded-full overflow-hidden" style="background: var(--bg-hover)">
    <div
      class="h-full rounded-full transition-all"
      style="width: {score}%; background: var(--accent-green)"
    ></div>
  </div>
  <span class="text-xs w-6 text-right" style="color: var(--text-muted)">{score}</span>
</div>
