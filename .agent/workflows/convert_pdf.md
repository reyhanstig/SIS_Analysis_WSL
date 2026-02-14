---
description: Convert a PDF file to Markdown context using the pdf_context_tool
---

1. Ensure the PDF file is located in `sources/papers/`.
2. Run the conversion tool:
   ```bash
   python sources/papers/pdf_context_tool.py <your_pdf_filename.pdf>
   ```
   *(Replace `<your_pdf_filename.pdf>` with the actual file name, e.g., "Ito 2004.pdf")*

3. The tool will generate a Markdown file in `sources/papers/context_store/<filename>.md` and extract images to `sources/papers/context_store/<filename>/`.

4. Open the generated Markdown file to verify the content.

5. You can now use this Markdown file and the extracted images in `sources/papers/context_store/<filename>/` as context for further tasks (e.g., summarization, analysis). Ensure you explicitly instruct the Agent to look at the images if they are relevant to your query.