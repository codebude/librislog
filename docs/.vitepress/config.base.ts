import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LibrisLog',
  vite: {
    server: {
      host: true,
      port: 5174,
      strictPort: true,
    },
  },
  description: 'Documentation for LibrisLog — a multi-user book tracking webapp',
  lang: 'en-US',
  lastUpdated: true,
  ignoreDeadLinks: [/^http:\/\/localhost/],
  markdown: {
    image: {
      lazyLoading: true,
    },
  },
  head: [
    ['link', { rel: 'icon', href: '/favicon.svg' }],
    ['script', { defer: '', 'data-domain': 'codebude.github.io/librislog', src: 'https://plausible.code-bude.net/js/script.js' }],
  ],
  themeConfig: {
    logo: '/logo.png',
    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'API', link: '/api/' },
      { text: 'About', link: '/about' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Quick Start', link: '/guide/getting-started' },
            { text: 'Configuration', link: '/guide/configuration' },
            { text: 'API Keys', link: '/guide/api-keys' },
            {
              text: 'Developer Setup',
              link: '/guide/developer-setup',
              collapsed: true,
              items: [
                { text: 'CLI Reference', link: '/guide/cli' },
              ],
            },
          ],
        },
        {
          text: 'Using LibrisLog',
          items: [
            { text: 'Dashboard', link: '/guide/using-librislog/dashboard' },
            { text: 'Library', link: '/guide/using-librislog/library' },
            { text: 'Profile', link: '/guide/using-librislog/profile' },
            { text: 'Progress Tracking', link: '/guide/using-librislog/progress' },
            { text: 'Statistics', link: '/guide/using-librislog/statistics' },
            { text: 'Import & Export', link: '/guide/using-librislog/import-export' },
            { text: 'Data Hygiene', link: '/guide/using-librislog/data-hygiene' },
            { text: 'Administration', link: '/guide/using-librislog/administration' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API Documentation',
          items: [
            { text: 'Overview', link: '/api/' },
            { text: 'Headless Setup & API Keys', link: '/api/setup' },
          ],
        },
      ],
    },
    search: { provider: 'local' },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/codebude/librislog' },
    ],
    footer: {
      message: 'Released under the MIT License.',
    },
  },
})
