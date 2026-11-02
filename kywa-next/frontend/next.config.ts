import type { NextConfig } from 'next';
const basePath = (process.env.APP_BASE_PATH || '').replace(/\/+$/, '');
if (basePath && !/^(\/[A-Za-z0-9_-]+)+$/.test(basePath)) throw new Error('Invalid APP_BASE_PATH');
const config: NextConfig = { output: 'export', trailingSlash: true, basePath,
  env: { NEXT_PUBLIC_APP_BASE_PATH: basePath }, images: { unoptimized: true } };
export default config;
