// Parse local browser modules without npm dependencies or executing their code.
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
let count = 0;
for (const directory of ['assets/home', 'assets/viewer']) {
  for (const name of readdirSync(resolve(root, directory)).sort()) {
    if (!name.endsWith('.js')) continue;
    const path = resolve(root, directory, name);
    const result = spawnSync(process.execPath, ['--input-type=module', '--check'], {
      input: readFileSync(path, 'utf8'),
      encoding: 'utf8',
    });
    if (result.error || result.status !== 0) {
      console.error(`${directory}/${name}: ${result.error || result.stderr}`);
      process.exitCode = 1;
    }
    count += 1;
  }
}
if (!process.exitCode) console.log(`JavaScript syntax passed: ${count} files.`);
