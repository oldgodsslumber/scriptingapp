// Copies the files the web app needs into .site/, the folder Firebase Hosting publishes.
// Runs automatically before `firebase deploy --only hosting` (see firebase.json).
//
// If private/firebase-config.js exists it replaces the repo's blank firebase-config.js, so a
// deployment's own config never has to be committed. Everything else (functions/, private/,
// uploads/, tests) stays out of the published site.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, '.site');
const FILES = ['index.html', 'support.js', 'firebase-config.js'];
const DIRS = ['assets'];

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
for (const f of FILES) cpSync(join(root, f), join(out, f));
for (const d of DIRS) cpSync(join(root, d), join(out, d), { recursive: true, filter: src => !/[\\/]\._/.test(src) });

const privateConfig = join(root, 'private', 'firebase-config.js');
if (existsSync(privateConfig)) {
  cpSync(privateConfig, join(out, 'firebase-config.js'));
  console.log('build-site: using private/firebase-config.js');
} else {
  console.log('build-site: no private/firebase-config.js, publishing the repo config');
}
console.log('build-site: wrote ' + out);
