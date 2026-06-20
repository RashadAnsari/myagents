---
name: markitdown
description: Convert files, URLs, and documents to Markdown using the markitdown MCP server. Activate when the user asks to convert, extract, or read content from PDFs, Word docs, PowerPoints, spreadsheets, images, audio files, YouTube URLs, or any local file.
---

# Markitdown: Convert Anything to Markdown

The `markitdown` MCP server exposes a single tool that converts a supported resource to Markdown.

## Tool

```
mcp__markitdown__convert_to_markdown(uri: string)
```

## Important: the MCP server has its own filesystem

The markitdown server does **not** share your bash/container filesystem. A `file://`
path that works in `bash` (e.g. anything under `/mnt/user-data/uploads/`, `/tmp/`,
or your working dir) will fail with "No such file or directory" when passed to this
tool. The server simply can't see those files.

So `file://` only works when the path is reachable by the *server*, which in this
environment is effectively never. Treat `file://` as not available, and use one of
the methods below instead.

## What the `uri` parameter accepts

| Scheme | Example | Status here |
|--------|---------|-------------|
| `https:` / `http:` | `https://example.com/page` | Works |
| `data:` | `data:application/pdf;base64,...` | Works (small files only) |
| `file:` | `file:///path/to/file.pdf` | Fails — server can't see your filesystem |

## Supported formats

PDF, Word, PowerPoint, Excel, HTML, CSV, JSON, XML, ZIP archives, EPubs, and
YouTube URLs convert fine.

Note: image OCR and audio transcription are advertised but do **not** work in this
environment — images return only metadata (no text), and audio returns nothing
useful. Don't rely on them. For text inside images, use a different OCR path.

## How to Use

### Remote URL or YouTube (preferred)

```
mcp__markitdown__convert_to_markdown(uri="https://example.com/report.pdf")
mcp__markitdown__convert_to_markdown(uri="https://www.youtube.com/watch?v=...")
```

### Local file — use a data: URI (the workaround for the filesystem issue)

Since `file://` fails, encode the local file as base64 in bash and pass it as a
`data:` URI:

```bash
b64=$(base64 -w0 /path/to/file.pdf)
echo "data:application/pdf;base64,$b64"
```

Then call:
```
mcp__markitdown__convert_to_markdown(uri="data:application/pdf;base64,<...>")
```

Use the correct MIME type for the file (`application/pdf`, `text/html`,
`text/csv`, `image/png`, etc.).

**Size limit:** a `data:` URI must fit inside one tool call, so this only works for
small files (roughly a few hundred KB). Large files produce millions of base64
characters and won't fit. For a large local file, don't use markitdown — use the
`pdf` / `file-reading` skills, or fetch it from a URL instead.

## After Conversion

The tool returns the Markdown as a string. Summarize it, answer questions about it,
or ask the user what they want next.
