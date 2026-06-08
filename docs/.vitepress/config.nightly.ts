import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/next/',
  head: [
    ...(baseConfig.head || []),
    ['link', { rel: 'icon', href: '/next/favicon.svg', type: 'image/svg+xml' }],
    ['link', { rel: 'alternate icon', href: '/next/favicon.ico', sizes: 'any' }],
  ],
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Release Docs', link: 'https://docs.librislog.app/' },
    ],
  },
})
