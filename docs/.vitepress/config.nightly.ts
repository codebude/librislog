import { defineConfig } from 'vitepress'
import baseConfig from './config.base'

export default defineConfig({
  ...baseConfig,
  base: '/librislog/next/',
  themeConfig: {
    ...baseConfig.themeConfig,
    nav: [
      ...(baseConfig.themeConfig?.nav || []),
      { text: 'Release Docs', link: 'https://librislog.codebude.at/librislog/' },
    ],
  },
})
