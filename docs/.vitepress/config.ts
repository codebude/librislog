import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/librislog/',
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Nightly Docs', link: 'https://librislog.codebude.at/librislog/next/' },
    ],
  },
})