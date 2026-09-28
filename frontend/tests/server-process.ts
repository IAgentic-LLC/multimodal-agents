import { spawn, type ChildProcess } from "node:child_process";

async function waitFor(url: string, child: ChildProcess): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`test server exited with code ${child.exitCode}`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The process is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`test server did not become ready: ${url}`);
}

export async function startServer(options: {
  args: string[];
  command: string;
  cwd: string;
  url: string;
}): Promise<() => Promise<void>> {
  const child = spawn(options.command, options.args, {
    cwd: options.cwd,
    stdio: "ignore",
    windowsHide: true,
  });
  await waitFor(options.url, child);
  return async () => {
    if (child.exitCode === null) child.kill();
    await new Promise<void>((resolve) => {
      if (child.exitCode !== null) return resolve();
      child.once("exit", () => resolve());
      setTimeout(resolve, 5_000);
    });
  };
}
