import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/librislog/next/',
  head: [
    ['link', { rel: 'icon', href: '/librislog/next/favicon.svg', type: 'image/svg+xml' }],
    ['link', { rel: 'alternate icon', href: '/librislog/next/favicon.ico', sizes: 'any' }],
  ],
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Release Docs', link: 'https://librislog.codebude.at/librislog/' },
    ],
  },
})
