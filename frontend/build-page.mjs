import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'
const sdk = fileURLToPath(new URL('.', import.meta.url))
const web = resolve(process.argv[2])
const require = createRequire(import.meta.url)
await build({
  configFile: false,
  root: web,
  base: './',
  plugins: [vue()],
  resolve: {
    alias: {
      vue: require.resolve('vue/dist/vue.runtime.esm-bundler.js'),
      '@sakubot/ui': resolve(sdk, 'src/plugin-sdk/index.ts'),
    },
  },
  build: { outDir: resolve(web, 'dist'), emptyOutDir: true, sourcemap: false },
})
