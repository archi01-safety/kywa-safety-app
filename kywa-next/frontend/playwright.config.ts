import { defineConfig } from '@playwright/test';
import path from 'node:path';
import os from 'node:os';
const prefix = process.env.APP_BASE_PATH || '';
export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  use: { baseURL: `http://localhost:8010${prefix}/`, browserName: 'chromium', channel: 'chromium', launchOptions: { timeout: 30000 }, trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `"${process.env.KYWA_TEST_PYTHON || 'python'}" app.py`,
    cwd: '..', url: `http://localhost:8010${prefix}/healthz`, reuseExistingServer: false,
    env: { PORT:'8010', HOST:'127.0.0.1', ORGANIZATION_ID: process.env.ORGANIZATION_ID || 'kywa', APP_ENV: 'demo', APP_BASE_PATH:prefix, APP_BASE_URL: 'http://localhost:8010', APP_DATA_DIR:path.join(os.tmpdir(),`safety-e2e-${Date.now()}`), DEMO_DATA_PATH: path.join(os.tmpdir(),`safety-e2e-${Date.now()}.json`) },
  },
});
