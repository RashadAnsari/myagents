---
name: markitdown
description: Convert files, URLs, and documents to Markdown using the markitdown MCP server. Activate when the user asks to convert, extract, or read content from PDFs, Word docs, PowerPoints, spreadsheets, images, audio files, or any URL.
allowed-tools: [mcp__plugin_albino_markitdown__convert_to_markdown]
---

# Markitdown: Convert Anything to Markdown

The `markitdown` MCP server exposes a single tool that converts any supported resource to Markdown.

## Tool

```
convert_to_markdown(uri: string)   # on the markitdown MCP server
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

- User says "convert this file to markdown", "read this PDF", "extract text from this Word doc"
- User pastes a file path and asks what is in it
- User wants to summarize or process a document before passing it to another tool
- User needs to index or search document content

## How to Use

**Local file:**
```
convert_to_markdown(
  uri="file:///absolute/path/to/file.pdf"
)
```

Always use an absolute path. Relative paths will fail.

**Remote URL:**
```
convert_to_markdown(
  uri="https://example.com/document"
)
```

## After Conversion

The tool returns the full Markdown content as a string. You can then:

- Write it to a `.md` file in the project with `Write`
- Summarize or process it inline
- Pass it to another tool or agent
