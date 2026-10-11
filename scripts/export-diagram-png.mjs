#!/usr/bin/env node
// Exports an Archify HTML diagram to PNG. Archify has no export command: PNG
// export lives only in the viewer's Export menu, so this opens the page in
// headless Chrome and clicks Export > PNG, capturing the file it downloads.
//
// Usage: node scripts/export-diagram-png.mjs <diagram.html> <output.png>
// Set CHROME to the Chrome executable when it is not in /Applications.

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const EXPORT_TIMEOUT_MS = 30_000;

// Runs inside the page. Waits for the viewer to load, clicks Export > PNG, and
// resolves with the downloaded PNG as base64 instead of saving it to disk.
function exportPngInPage(timeoutMs) {
  return new Promise((done, fail) => {
    const start = () => {
      HTMLAnchorElement.prototype.click = function () {
        fetch(this.href)
          .then((response) => response.blob())
          .then((blob) => {
            const reader = new FileReader();
            reader.onload = () => done(reader.result.split(",")[1]);
            reader.readAsDataURL(blob);
          }, fail);
      };
      document.getElementById("btn-export").click();
      document.querySelector('#export-menu [data-format="png"]').click();
    };

    if (document.readyState === "complete") start();
    else addEventListener("load", start);
    setTimeout(() => fail(new Error("PNG export timed out")), timeoutMs);
  });
}

function launchChrome(profileDir) {
  const executable = process.env.CHROME || DEFAULT_CHROME;
  return spawn(
    executable,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      `--user-data-dir=${profileDir}`,
      "--no-first-run",
      "--window-size=1600,1000",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
}

// Chrome picks a free port and prints it on stderr once DevTools is ready.
function waitForDevToolsPort(chrome) {
  return new Promise((ok, fail) => {
    let log = "";
    chrome.stderr.on("data", (chunk) => {
      log += chunk;
      const match = log.match(/DevTools listening on ws:\/\/[^:]+:(\d+)\//);
      if (match) ok(match[1]);
    });
    chrome.once("error", fail);
    chrome.once("exit", () =>
      fail(new Error(`Chrome exited before it was ready. Set CHROME to its path.\n${log}`)),
    );
  });
}

async function openPage(port, url) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${url}`, { method: "PUT" });
  const target = await response.json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok) => socket.addEventListener("open", ok, { once: true }));
  return socket;
}

function evaluate(socket, expression) {
  return new Promise((ok) => {
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id === 1) ok(message);
    });
    socket.send(
      JSON.stringify({
        id: 1,
        method: "Runtime.evaluate",
        params: { expression, awaitPromise: true, returnByValue: true },
      }),
    );
  });
}

async function main() {
  const [htmlPath, pngPath] = process.argv.slice(2);
  if (!htmlPath || !pngPath) {
    console.error("Usage: node scripts/export-diagram-png.mjs <diagram.html> <output.png>");
    process.exit(2);
  }

  const profileDir = mkdtempSync(join(tmpdir(), "export-diagram-"));
  const chrome = launchChrome(profileDir);
  try {
    const port = await waitForDevToolsPort(chrome);
    const socket = await openPage(port, pathToFileURL(resolve(htmlPath)).href);
    const reply = await evaluate(socket, `(${exportPngInPage})(${EXPORT_TIMEOUT_MS})`);
    socket.close();

    const base64 = reply.result?.result?.value;
    if (!base64) {
      const details = reply.result?.exceptionDetails ?? reply.error;
      throw new Error(`PNG export failed: ${JSON.stringify(details)}`);
    }
    writeFileSync(pngPath, Buffer.from(base64, "base64"));
    console.log(`Wrote ${pngPath}`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    chrome.kill();
    rmSync(profileDir, { recursive: true, force: true });
  }
}

await main();
