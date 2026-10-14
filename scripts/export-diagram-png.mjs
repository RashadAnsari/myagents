#!/usr/bin/env node
// Exports an Archify HTML diagram to PNG in the dark theme. Archify has no
// export command: PNG export lives only in the viewer's Export menu, so this
// opens the page in headless Chrome and clicks Export > PNG, capturing the
// file it downloads.
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
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: "PUT" });
  const target = await response.json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((ok) => socket.addEventListener("open", ok, { once: true }));
  return socket;
}

let nextMessageId = 1;

function evaluate(socket, expression) {
  const id = nextMessageId++;
  return new Promise((ok) => {
    const onMessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      socket.removeEventListener("message", onMessage);
      ok(message);
    };
    socket.addEventListener("message", onMessage);
    socket.send(
      JSON.stringify({
        id,
        method: "Runtime.evaluate",
        params: { expression, awaitPromise: true, returnByValue: true },
      }),
    );
  });
}

// A new tab starts on about:blank and navigates afterwards, so the export
// script must wait until the viewer itself has loaded.
async function waitForViewer(socket) {
  const ready = `document.readyState === "complete" && !!document.getElementById("btn-export")`;
  const deadline = Date.now() + EXPORT_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const reply = await evaluate(socket, ready);
    if (reply.result?.result?.value === true) return;
    await new Promise((ok) => setTimeout(ok, 100));
  }
  throw new Error("The diagram page did not load in time.");
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
    // Without ?theme=dark the viewer follows the system color scheme, which
    // differs between machines (headless Chrome on Linux reports light).
    const pageUrl = pathToFileURL(resolve(htmlPath));
    pageUrl.searchParams.set("theme", "dark");
    const socket = await openPage(port, pageUrl.href);
    await waitForViewer(socket);
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
    // Chrome can still be writing to its profile right after kill(), so retry.
    rmSync(profileDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

await main();
