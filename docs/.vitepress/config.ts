import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'LibrisLog',
  description: 'Documentation for LibrisLog — a single-user book tracking webapp',
  base: '/librislog/',
  lang: 'en-US',
  lastUpdated: true,
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
            { text: 'Installation', link: '/guide/installation' },
            { text: 'Configuration', link: '/guide/configuration' },
          ],
        },
        {
          text: 'Using LibrisLog',
          items: [
            { text: 'Library', link: '/guide/using-librislog/library' },
            { text: 'Progress Tracking', link: '/guide/using-librislog/progress' },
            { text: 'Statistics', link: '/guide/using-librislog/statistics' },
            { text: 'Import & Export', link: '/guide/using-librislog/import-export' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API Documentation',
          items: [
            { text: 'Overview', link: '/api/' },
          ],
        },
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/codebude/librislog' },
    ],
    footer: {
      message: 'Released under the MIT License.',
    },
  },
})