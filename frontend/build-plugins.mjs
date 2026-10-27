import { build } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { readdir, access } from 'node:fs/promises'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'

const root = fileURLToPath(new URL('.', import.meta.url))
const roots = process.argv[2] ? [resolve(process.argv[2])] : [resolve(root, '../sakubot/system'), resolve(root, '../sakubot/plugins')]
const require = createRequire(import.meta.url)
for (const plugins of roots) {
for (const entry of await readdir(plugins, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue
  const web = resolve(plugins, entry.name, 'web')
  try {
    await access(resolve(web, 'index.html'))
  } catch {
    continue
  }
  await build({
    configFile: false,
    root: web,
    base: './',
    plugins: [vue()],
    resolve: {
      alias: {
        vue: require.resolve('vue/dist/vue.runtime.esm-bundler.js'),
        '@sakubot/ui': resolve(root, 'src/plugin-sdk/index.ts'),
      },
    },
    build: { outDir: resolve(web, 'dist'), emptyOutDir: true, sourcemap: false },
  })
}

}
