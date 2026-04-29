<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';

  let { children } = $props();

  const navLinks = [
    { href: '/',        label: 'Overview',        icon: '⊞' },
    { href: '/artists', label: 'Top Artists',      icon: '🎤' },
    { href: '/tracks',  label: 'Top Tracks',       icon: '🎵' },
    { href: '/recent',  label: 'Recently Played',  icon: '🕐' },
  ];
</script>

<div class="flex h-screen overflow-hidden" style="background: var(--bg-base)">
  <!-- Sidebar -->
  <nav class="w-60 flex-shrink-0 flex flex-col py-6 px-4 gap-1" style="background: #000">
    <!-- Logo -->
    <div class="flex items-center gap-2 px-3 mb-6">
      <svg viewBox="0 0 24 24" class="w-8 h-8" fill="var(--accent-green)">
        <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
      </svg>
      <span class="font-bold text-sm tracking-wide" style="color: var(--text-primary)">data-world</span>
    </div>

    <!-- Nav links -->
    {#each navLinks as link}
      {@const active = $page.url.pathname === link.href}
      <a
        href={link.href}
        class="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors"
        style={active
          ? 'background: var(--bg-highlight); color: var(--text-primary)'
          : 'color: var(--text-muted)'}
      >
        <span class="text-base">{link.icon}</span>
        {link.label}
        {#if active}
          <span class="ml-auto w-1 h-4 rounded-full" style="background: var(--accent-green)"></span>
        {/if}
      </a>
    {/each}
  </nav>

  <!-- Main content -->
  <main class="flex-1 overflow-y-auto">
    {@render children()}
  </main>
</div>
