# NCCN Guidelines MCP Server

A Model Context Protocol (MCP) server that provides access to NCCN (National Comprehensive Cancer Network) clinical guidelines.

## Features

- **Guidelines Index**: Automatically fetches and maintains an up-to-date index of NCCN guidelines
- **PDF Download**: Downloads NCCN guideline PDFs with authentication support
- **Content Extraction**: Extracts specific pages from PDF documents with layout preservation
- **Smart Caching**: Index is cached for 7 days to minimize server load

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure NCCN credentials (optional but recommended):

**Option A: Use the configuration script (recommended)**
```bash
python setup_config.py
```

**Option B: Set environment variables manually**
```bash
export NCCN_USERNAME="your_email@example.com"
export NCCN_PASSWORD="your_password_here"
```

**Option C: Create a `.env` file in the `guideline_new` directory**
```env
NCCN_USERNAME=your_email@example.com
NCCN_PASSWORD=your_password_here
```

3. Run the server:
```bash
python server.py
```

### Authentication Configuration

The server supports NCCN authentication through environment variables:

- **NCCN_USERNAME**: Your NCCN account email
- **NCCN_PASSWORD**: Your NCCN account password

If these are not set, the server will still work but may have limited access to some premium NCCN content. You can also provide credentials directly when calling the `download_pdf` tool.

## MCP Configuration

To use with Claude for Desktop, add this to your `claude_desktop_config.json`:

### Basic Configuration
```json
{
  "mcpServers": {
    "nccn-guidelines": {
      "command": "python",
      "args": ["/absolute/path/to/guideline_new/server.py"]
    }
  }
}
```

### Configuration with Environment Variables
```json
{
  "mcpServers": {
    "nccn-guidelines": {
      "command": "python",
      "args": ["/absolute/path/to/guideline_new/server.py"],
      "env": {
        "NCCN_USERNAME": "your_email@example.com",
        "NCCN_PASSWORD": "your_password_here"
      }
    }
  }
}
```

**Note**: For security, it's recommended to set environment variables in your system rather than directly in the configuration file.

## Available Resources

- `nccn://guidelines-index`: Access the complete NCCN guidelines index

## Available Prompts

- `nccn-usage-guide`: Comprehensive guide on how to use the server

## Available Tools

1. **download_pdf**: Download NCCN guideline PDFs
   - `url`: PDF URL to download
   - `filename` (optional): Custom filename
   - `username` (optional): NCCN login username (defaults to NCCN_USERNAME env var)
   - `password` (optional): NCCN login password (defaults to NCCN_PASSWORD env var)

2. **extract_content**: Extract content from PDF pages
   - `pdf_path`: Path to PDF file
   - `pages` (optional): Comma-separated page numbers (e.g., "1,3,5-7")

## Usage Example

1. Ask the assistant to find guidelines for a specific condition
2. The assistant will search the index and download the relevant PDF
3. The assistant will extract relevant content from specific pages
4. You'll receive evidence-based recommendations with page references

## Initialization

On first run, the server will:
- Fetch the latest NCCN guidelines index from the NCCN website
- Cache the index locally for 7 days
- Display initialization status and guideline counts

## Notes

- Some NCCN PDFs require authentication - provide credentials when needed
- PDF extraction preserves layout but may need interpretation for flowcharts
- Index is automatically refreshed every 7 days 