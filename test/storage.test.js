const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { ensureDataFiles, readJson, writeJson } = require('../server');

test('ensureDataFiles creates JSON stores', () => {
  const tempDir = path.join(__dirname, 'tmp-data');
  const tempUsers = path.join(tempDir, 'users.json');
  const tempEntries = path.join(tempDir, 'entries.json');
  if (fs.existsSync(tempDir)) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  const originalDir = process.cwd();
  process.chdir(__dirname);
  try {
    const dataDir = path.join(__dirname, 'tmp-data');
    const usersFile = path.join(dataDir, 'users.json');
    const entriesFile = path.join(dataDir, 'entries.json');

    const oldDir = process.cwd();
    process.chdir(__dirname);
    try {
      ensureDataFiles();
      assert.ok(fs.existsSync(usersFile));
      assert.ok(fs.existsSync(entriesFile));
      assert.deepEqual(readJson(usersFile), []);
      assert.deepEqual(readJson(entriesFile), []);
      writeJson(usersFile, [{ id: '1', username: 'alice' }]);
      assert.equal(readJson(usersFile)[0].username, 'alice');
    } finally {
      process.chdir(oldDir);
    }
  } finally {
    process.chdir(originalDir);
  }
});
