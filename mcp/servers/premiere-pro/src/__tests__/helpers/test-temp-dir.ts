/**
 * Every test worker gets its own PREMIERE_TEMP_DIR under os.tmpdir(). Without
 * this, tools that generate assets (adjustment layers, demo media) fall back to
 * the real per-user bridge directory and leave test PNGs there.
 */
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const dir = mkdtempSync(join(tmpdir(), 'premiere-mcp-test-'));
process.env.PREMIERE_TEMP_DIR = dir;

afterAll(() => {
  rmSync(dir, { recursive: true, force: true });
});
