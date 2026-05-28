import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/librislog/',
  head: [
    ...(baseConfig.head || []),
    ['link', { rel: 'icon', href: '/librislog/favicon.svg', type: 'image/svg+xml' }],
    ['link', { rel: 'alternate icon', href: '/librislog/favicon.ico', sizes: 'any' }],
  ],
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Nightly Docs', link: 'https://codebude.github.io/librislog/next/' },
    ],
  },
})