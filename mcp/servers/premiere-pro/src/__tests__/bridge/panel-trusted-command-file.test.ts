/**
 * The panel executes whatever command-*.json appears in the bridge directory,
 * so a file planted by another local user or process must never reach
 * evalScript. isTrustedCommandFile() accepts only a regular file owned by the
 * current user that group/others cannot write; anything else is removed and
 * skipped. validateScript() must also reject ExtendScript escape hatches that
 * reach the shell or load code from disk.
 */

import { loadPanel } from '../helpers/panel.js';

type Stat = {
  uid: number; mode: number;
  isSymbolicLink: () => boolean; isFile: () => boolean; isDirectory: () => boolean;
};

function stat(overrides: Partial<Stat> = {}): Stat {
  return {
    uid: process.getuid ? process.getuid() : 0,
    mode: 0o100600,
    isSymbolicLink: () => false,
    isFile: () => true,
    isDirectory: () => false,
    ...overrides,
  };
}

const posixOnly = process.platform === 'win32' ? describe.skip : describe;

posixOnly('isTrustedCommandFile', () => {
  const setup = (s: Stat) => {
    const panel = loadPanel();
    const fs = panel.fs as unknown as { lstatSync: jest.Mock; unlinkSync: jest.Mock };
    fs.lstatSync = jest.fn(() => s);
    fs.unlinkSync = jest.fn();
    return { panel, fs };
  };

  it('accepts a regular file owned by this user with mode 0600', () => {
    const { panel, fs } = setup(stat());
    expect(panel.bridge.isTrustedCommandFile('/bridge/command-1.json')).toBe(true);
    expect(fs.unlinkSync).not.toHaveBeenCalled();
  });

  it.each([
    ['a symlink', stat({ isSymbolicLink: () => true })],
    ['a file owned by another user', stat({ uid: (process.getuid ? process.getuid() : 0) + 1 })],
    ['a group-writable file', stat({ mode: 0o100620 })],
    ['a world-writable file', stat({ mode: 0o100602 })],
    ['a non-regular file', stat({ isFile: () => false })],
  ])('rejects and removes %s', (_label, s) => {
    const { panel, fs } = setup(s);
    expect(panel.bridge.isTrustedCommandFile('/bridge/command-1.json')).toBe(false);
    expect(fs.unlinkSync).toHaveBeenCalledWith('/bridge/command-1.json');
  });

  it('rejects a file that vanished before it could be inspected', () => {
    const panel = loadPanel();
    (panel.fs as unknown as { lstatSync: () => never }).lstatSync = () => { throw new Error('ENOENT'); };
    expect(panel.bridge.isTrustedCommandFile('/bridge/command-1.json')).toBe(false);
  });
});

describe('validateScript ExtendScript escape hatches', () => {
  const { bridge } = loadPanel();
  it.each([
    'system.callSystem("open -a Calculator")',
    'new File("/tmp/x.sh").execute()',
    '$.evalFile("/tmp/x.jsx")',
    '#include "/tmp/x.jsx"',
    '#includepath "/tmp"',
    'app.doScript("1")',
  ])('rejects %s', (script) => {
    expect(bridge.validateScript(`var a = 1;\n${script}`)).toBe(false);
  });

  it('still accepts ordinary project scripting', () => {
    expect(bridge.validateScript('var seq = app.project.activeSequence; JSON.stringify({ name: seq.name });')).toBe(true);
  });
});

describe('validateScript only inspects code, not literals or comments', () => {
  const { bridge } = loadPanel();
  it.each([
    'var title = "callSystem";',
    "var name = 'doScript';",
    'app.project.importFiles(["/media/doScript.mp4"]);',
    'var label = "run .execute( later";',
    '// system.callSystem is intentionally unavailable here\nvar a = 1;',
    '/* $.evalFile("x") is blocked */ var b = 2;',
    'var s = "quote \\" then callSystem";',
  ])('accepts %s', (script) => {
    expect(bridge.validateScript(script)).toBe(true);
  });

  it('still rejects the call when a literal merely precedes it', () => {
    expect(bridge.validateScript('var t = "safe"; system.callSystem("open -a Calculator")')).toBe(false);
  });

  it('rejects an unterminated literal that tries to hide a call after a newline', () => {
    expect(bridge.validateScript('var t = "open\nsystem.callSystem("x")')).toBe(false);
  });
});
