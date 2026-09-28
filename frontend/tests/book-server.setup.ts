import path from "node:path";
import { fileURLToPath } from "node:url";

import { startServer } from "./server-process";

export default async function setup(): Promise<() => Promise<void>> {
  const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
  const repository = path.dirname(frontend);
  const book = path.resolve(repository, "..", "multimodal-agents-book", "_book");
  return startServer({
    command: path.join(repository, ".venv", "Scripts", "python.exe"),
    args: ["-m", "http.server", "8770", "--bind", "127.0.0.1", "--directory", book],
    cwd: repository,
    url: "http://127.0.0.1:8770",
  });
}
