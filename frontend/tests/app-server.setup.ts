import path from "node:path";
import { fileURLToPath } from "node:url";

import { startServer } from "./server-process";

export default async function setup(): Promise<() => Promise<void>> {
  const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const repository = path.dirname(frontend);
  return startServer({
    command: path.join(repository, ".venv", "Scripts", "python.exe"),
    args: ["-m", "multimodal_agents.server", "--port", "8765"],
    cwd: repository,
    url: "http://127.0.0.1:8765",
  });
}
