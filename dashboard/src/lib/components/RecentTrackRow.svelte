<script lang="ts">
  import type { RecentPlay } from '$lib/types';

  let { play }: { play: RecentPlay } = $props();

  const relativeTime = $derived(() => {
    const diff = Date.now() - new Date(play.played_at).getTime();
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(mins / 60);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (mins > 0) return `${mins}m ago`;
    return 'Just now';
  });
</script>

<div class="flex items-center gap-4 py-3 border-b" style="border-color: var(--border)">
  <div class="flex-1 min-w-0">
    <a
      href={play.spotify_url}
      target="_blank"
      rel="noopener noreferrer"
      class="font-medium text-sm truncate block hover:underline"
      style="color: var(--text-primary)"
    >
      {play.track_name}
    </a>
    <p class="text-xs truncate mt-0.5" style="color: var(--text-muted)">{play.artist_names}</p>
  </div>
  <div class="flex-shrink-0 text-right">
    <p class="text-xs" style="color: var(--text-subdued)">{relativeTime()}</p>
    {#if play.context_type}
      <p class="text-xs capitalize mt-0.5" style="color: var(--text-subdued)">{play.context_type}</p>
    {/if}
  </div>
</div>
