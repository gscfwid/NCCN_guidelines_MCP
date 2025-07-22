# 🏥 NCCN Guidelines MCP Server

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-v1.11.0-green.svg)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)](https://github.com/gscfwid/nccn_mcp/releases)

[![PyPDF](https://img.shields.io/badge/PyPDF-5.8.0+-lightblue.svg)](https://pypdf.readthedocs.io/)
[![HTTPX](https://img.shields.io/badge/HTTPX-async-purple.svg)](https://www.python-httpx.org/)
[![NCCN](https://img.shields.io/badge/NCCN-Guidelines-red.svg)](https://www.nccn.org/)

A Model Context Protocol (MCP) server that provides access to NCCN (National Comprehensive Cancer Network) clinical guidelines.

## 🔬 How It Works

This project follows a systematic approach to provide accurate medical guidance:
1. **🧠 Problem Analysis**: Understands the clinical question or scenario
2. **📋 Guidelines Retrieval**: Searches the NCCN index for relevant guidelines
3. **📄 Page-by-Page Reading**: Downloads and extracts specific pages from guidelines
4. **🎯 Evidence-Based Response**: Provides answers based on the extracted content

**💡 Note**: This system does not use RAG (Retrieval-Augmented Generation) to ensure accuracy. Instead, it reads guidelines directly, which may result in longer response times during index initialization and PDF downloading/reading, but provides more reliable and precise medical guidance.

## ✨ Features

- **📚 Guidelines Index**: Automatically fetches and maintains an up-to-date index of NCCN guidelines
- **⬇️ PDF Download**: Downloads NCCN guideline PDFs with authentication support
- **📝 Content Extraction**: Extracts specific pages from PDF documents with layout preservation
- **🚀 Smart Caching**: Index is cached for 7 days to minimize server load

## 🛠️ Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd NCCN_guidelines_MCP
```

2. Install dependencies using uv:
```bash
uv sync
```

## ⚙️ Configuration

### 🔧 Configure Client (Note: Supports only agents, such as Cursor, Cline, Claude desktop, etc.)

**⚠️ Important**: Claude desktop may warn about insufficient context length when running this MCP.

Add this to your Client configuration:

**Configuration with Environment Variables**
```json
{
  "mcpServers": {
    "nccn-guidelines": {
      "command": "uv",
      "args": ["--directory", "<abslute_direction_of_NCCN_guidelines_MCP>", "run", "server.py"],
      "env": {
        "NCCN_USERNAME": "<your_nccn_username>",
        "NCCN_PASSWORD": "<your_nccn_password>"
      }
    }
  }
}
```

### ⚠️ Important Notes

- **👤 NCCN Account Registration**: Please note that the NCCN username and password mentioned above must be registered on the official NCCN website.
- **🚀 First-time Setup**: When you first start the MCP server, it needs to generate the YAML index of NCCN guidelines. This process takes 1-2 minutes, so please wait before attempting to use the server.
- **⏱️ Response Times**: Due to the non-RAG approach for accuracy, expect longer response times during guideline downloading and PDF reading processes.

## 💬 Prompts

To have better response, please add the prompt in the file of [`prompt.md`](./prompt.md) to the instruction of your Agent Client before your Question.

## 🛠️ Available Tools

1. **📊 get_index**: Get the raw contents of the NCCN guidelines index YAML file.

2. **📥 download_pdf**: Download NCCN guideline PDFs
   - `url`: PDF URL to download
   - `filename` (optional): Custom filename
   - `username` (optional): NCCN login username (defaults to NCCN_USERNAME env var)
   - `password` (optional): NCCN login password (defaults to NCCN_PASSWORD env var)

3. **📖 extract_content**: Extract content from PDF pages
   - `pdf_path`: Path to PDF file
   - `pages` (optional): Comma-separated page numbers (e.g., "1,3,5-7")

## 💡 Usage Example

Here are some example questions you can ask:

1. 🔬 What are the available first-line immunotherapy options for ES-SCLC?
2. 🎯 What is the initial chemotherapy for triple-negative breast cancer?
3. 🧬 What are the immunotherapy options for neuroendocrine tumors?
