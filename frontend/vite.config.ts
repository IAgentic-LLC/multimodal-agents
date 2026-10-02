import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: "node_modules/@itk-wasm/image-io/dist/pipelines/*.{js,wasm,wasm.zst}",
          dest: "pipelines/",
          rename: { stripBase: true },
        },
      ],
    }),
  ],
  optimizeDeps: {
    exclude: ["itk-wasm", "@itk-wasm/image-io", "@thewtex/zstddec"],
  },
  build: {
    outDir: resolve(
      import.meta.dirname,
      "../src/multimodal_agents/web",
    ),
    emptyOutDir: true,
  },
});
