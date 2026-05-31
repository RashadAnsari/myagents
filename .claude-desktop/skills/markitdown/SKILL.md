---
name: markitdown
description: Convert files, URLs, and documents to Markdown using the markitdown MCP server. Activate when the user asks to convert, extract, or read content from PDFs, Word docs, PowerPoints, spreadsheets, images, audio files, YouTube URLs, or any local file.
---

# Markitdown: Convert Anything to Markdown

The `markitdown` MCP server exposes a single tool that converts any supported resource to Markdown.

## Tool

```
mcp__markitdown__convert_to_markdown(uri: string)
```

The `uri` parameter accepts:

| Scheme | Example | Use for |
|--------|---------|---------|
| `file:` | `file:///Users/you/report.pdf` | Local files on disk |
| `https:` / `http:` | `https://example.com/page` | Web pages and remote documents |
| `data:` | `data:text/html;base64,...` | Inline base64-encoded content |

## Supported Formats

PDF, Word, PowerPoint, Excel, HTML, CSV, JSON, XML, ZIP archives, images (with EXIF metadata and OCR), audio (with speech transcription), EPubs, and YouTube URLs.

## When to Use

- User says "convert this file", "read this PDF", "extract text from this Word doc"
- User drops a file path into the conversation and wants its contents
- User shares a YouTube link and wants a transcript or summary
- User wants to read or process a document before discussing it

## How to Use

**Local file:**
```
mcp__markitdown__convert_to_markdown(
  uri="file:///absolute/path/to/file.pdf"
)
```

Always use an absolute path. Relative paths will fail.

**Remote URL or YouTube:**
```
mcp__markitdown__convert_to_markdown(
  uri="https://www.youtube.com/watch?v=..."
)
```

## After Conversion

The tool returns the full Markdown content as a string. You can then summarize it, answer questions about it, or ask the user what they want to do with it.
