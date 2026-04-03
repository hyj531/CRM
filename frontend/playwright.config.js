import { defineConfig } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173/app'
const useExistingServer = process.env.E2E_USE_EXISTING_SERVER === '1'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  use: {
    baseURL,
    trace: 'retain-on-failure'
  },
  webServer: useExistingServer
    ? undefined
    : {
        command: 'npm run dev -- --host 127.0.0.1 --port 5173',
        url: `${baseURL}/`,
        reuseExistingServer: true,
        timeout: 120_000
      }
})
