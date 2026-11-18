// Netlify: 0 skips a build, 1 builds. Documentation/evidence updates need no production deploy.
import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const previous = process.env.CACHED_COMMIT_REF, current = process.env.COMMIT_REF;
if (!previous || !current || previous === current) process.exit(1);
if (![previous, current].every((value) => /^[a-f0-9]{40}$/i.test(value))) process.exit(1);
const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const runtime = ['site', 'netlify.toml', 'tools/check.mjs', 'tools/ignore-build.mjs'].map((path) => `kywa-next/entry-screen/${path}`);
const result = spawnSync('git', ['diff', '--quiet', previous, current, '--', ...runtime], { cwd: repo, stdio: 'ignore' });
process.exit(result.status === 0 ? 0 : 1);
