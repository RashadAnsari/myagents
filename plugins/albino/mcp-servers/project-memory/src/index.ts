#!/usr/bin/env bun
import { runServer } from "./server.js";

runServer().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
