---
name: browsing_the_web
description: Workflow and best practices for using a browser subagent to navigate, scrape, and summarize web content in a WSL/Remote environment.
metadata:
  version: "1.0"
  type: workflow_guide
---

# Browsing the Web with Subagents

This skill provides instructions for effectively using the browser subagent to research and extract information from the web, especially when working within WSL.

## Workflow Steps

### 1. Environment Preparation
Ensure a Chrome instance is running with remote debugging enabled:
`google-chrome --headless --remote-debugging-port=9222 --no-sandbox &`
If the browser is on the host (Windows) and being accessed by WSL, use `socat` to bridge the connection to `localhost:9222`.

### 2. Navigation and Inspection
*   **Access**: Use `open_browser_url` to navigate to the target page.
*   **Verification**: Always call `read_browser_page` or `browser_get_dom` after a reload to verify the page content.
*   **Visual Check**: If the DOM seems incomplete or blocked, use `capture_browser_screenshot` to identify UI-based blockers (like captchas).

### 3. Handling Bot Detection (Anti-Scraping)
If blocked by Cloudflare or ReCAPTCHA:
1.  **RSS Feeds**: Try accessing `/feed` or `/rss` versions of the publication (extremely effective for Medium/blogs).
2.  **Caches/Archivers**: Use Google Cache (`webcache.googleusercontent.com`) or the Wayback Machine.
3.  **Proxies**: Use "readability" proxies like `archive.ph` or `google translate` as a ref-shuffler.
4.  **JSON Endpoints**: Append `?format=json` to URLs to see if an API response is available.

### 4. Data Extraction
*   Use `execute_browser_javascript` for precise extraction of specific elements (e.g., finding a title in an XML feed or clicking through a "Read More" button).
*   Use `browser_scroll` to trigger lazy-loading content before reading the full page.

## Best Practices
*   **Progressive Reading**: First identify if any navigation is needed, then read the metadata, then extract the full text.
*   **Token Management**: Do not read the entire DOM if only a specific article section is needed; use JS queries to narrowly target content.
*   **Security**: Never attempt to bypass auth or solve captchas directly. If a hard block is encountered, inform the user and suggest alternative sources.
