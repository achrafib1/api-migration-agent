import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

/** Keep Vitest module resolution aligned with the strict Next.js path alias. */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    clearMocks: true,
    restoreMocks: true,
  },
});
