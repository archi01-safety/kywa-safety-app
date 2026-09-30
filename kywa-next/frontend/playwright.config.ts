import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  use: { baseURL: 'http://localhost:8010', browserName: 'chromium', channel: 'chromium', launchOptions: { timeout: 30000 }, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `"${process.env.KYWA_TEST_PYTHON || 'python'}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8010`,
    cwd: '..', url: 'http://localhost:8010/healthz', reuseExistingServer: false,
    env: { APP_ENV: 'demo', APP_BASE_URL: 'http://localhost:8010', DEMO_DATA_PATH: `local-data/e2e-${Date.now()}.json` },
  },
});
