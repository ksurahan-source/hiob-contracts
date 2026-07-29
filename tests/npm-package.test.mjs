import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

function run(command, args, cwd) {
  return spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    env: { ...process.env, npm_config_audit: 'false', npm_config_fund: 'false' },
  });
}

test('repository root installs as @hiob/contracts with its built runtime', () => {
  const repositoryRoot = fileURLToPath(new URL('..', import.meta.url));
  const temporaryRoot = mkdtempSync(join(tmpdir(), 'hiob-contracts-package-'));
  const consumerRoot = join(temporaryRoot, 'consumer');
  mkdirSync(consumerRoot);

  try {
    const packed = run(
      'npm',
      ['pack', '--json', '--silent', '--pack-destination', temporaryRoot],
      repositoryRoot,
    );
    assert.equal(packed.status, 0, packed.stderr || packed.stdout);
    const [{ filename, files }] = JSON.parse(packed.stdout);
    const unexpected = files
      .map(({ path }) => path)
      .filter((path) => (
        path !== 'README.md'
        && path !== 'package.json'
        && !/^ts\/dist\/.+\.(?:js|d\.ts)$/.test(path)
      ));
    assert.deepEqual(unexpected, []);
    assert.equal(files.some(({ path }) => path.includes('.test.')), false);

    writeFileSync(
      join(consumerRoot, 'package.json'),
      JSON.stringify({ private: true, type: 'module' }),
    );
    const installed = run(
      'npm',
      ['install', '--ignore-scripts', join(temporaryRoot, filename)],
      consumerRoot,
    );
    assert.equal(installed.status, 0, installed.stderr || installed.stdout);

    const imported = run(
      'node',
      [
        '--input-type=module',
        '--eval',
        "import { CharacterLockV1Schema } from '@hiob/contracts';"
          + " if (!CharacterLockV1Schema) process.exit(2);",
      ],
      consumerRoot,
    );
    assert.equal(imported.status, 0, imported.stderr || imported.stdout);
  } finally {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
});
