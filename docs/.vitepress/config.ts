import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/',
  head: [
    ...(baseConfig.head || []),
    ['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }],
    ['link', { rel: 'alternate icon', href: '/favicon.ico', sizes: 'any' }],
  ],
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Nightly Docs', link: 'https://docs.librislog.app/next/' },
    ],
  },
})
