import { writeFileSync } from 'node:fs';
const basePath = (process.env.APP_BASE_PATH || '').replace(/\/+$/, '');
writeFileSync(new URL('../out/build-config.json', import.meta.url), JSON.stringify({basePath, format:1})+'\n');
