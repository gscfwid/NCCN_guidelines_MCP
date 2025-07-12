#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCCN Guidelines MCP Server

This server provides access to NCCN (National Comprehensive Cancer Network) guidelines
through the Model Context Protocol (MCP). It allows users to search for relevant
guidelines, download them, and extract specific content from the PDFs.

Configuration:
    Set the following environment variables for NCCN authentication:
    - NCCN_USERNAME: Your NCCN username/email
    - NCCN_PASSWORD: Your NCCN password
"""

import os
import sys
import yaml
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

# Add the current directory to the Python path for imports
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

from mcp.server.fastmcp import FastMCP
from read_pdf import PDFReader
from nccn_login_downloader import NCCNDownloader
from nccn_get_index import ensure_nccn_index

# Constants
GUIDELINES_INDEX_FILE = "nccn_guidelines_index.yaml"
DOWNLOAD_DIR = "downloads"

# Global configuration from environment variables
NCCN_USERNAME = os.getenv('NCCN_USERNAME')
NCCN_PASSWORD = os.getenv('NCCN_PASSWORD')

# Initialize FastMCP server
mcp = FastMCP("nccn-guidelines")

# Global instances
pdf_reader = PDFReader()
downloader = NCCNDownloader()

async def initialize_server():
    """
    Initialize the MCP server by ensuring the NCCN guidelines index is available.
    This function will download/update the index if needed.
    """
    print("Initializing NCCN Guidelines MCP Server...")
    
    # Display authentication status
    if NCCN_USERNAME and NCCN_PASSWORD:
        print(f"✓ NCCN authentication configured for user: {NCCN_USERNAME}")
    else:
        print("⚠ NCCN authentication not configured. Some features may be limited.")
        print("  Set NCCN_USERNAME and NCCN_PASSWORD environment variables for full access.")
    
    try:
        # Ensure the guidelines index exists and is up to date
        guidelines_data = await ensure_nccn_index(
            output_file=str(current_dir / GUIDELINES_INDEX_FILE),
            max_age_days=7  # Refresh index every 7 days
        )
        
        if guidelines_data:
            total_categories = len(guidelines_data.get('nccn_guidelines', []))
            total_guidelines = sum(
                len(cat.get('guidelines', [])) 
                for cat in guidelines_data.get('nccn_guidelines', [])
            )
            print(f"✓ NCCN Guidelines index ready: {total_categories} categories, {total_guidelines} guidelines")
        else:
            print("⚠ Warning: Could not load NCCN guidelines index")
            
    except Exception as e:
        print(f"⚠ Warning: Error initializing guidelines index: {str(e)}")
        print("The server will continue but may have limited functionality")
    
    print("NCCN Guidelines MCP Server initialization complete!")

def load_guidelines_index() -> Dict[str, Any]:
    """Load the NCCN guidelines index from YAML file."""
    index_path = current_dir / GUIDELINES_INDEX_FILE
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"error": "Guidelines index file not found"}
    except yaml.YAMLError as e:
        return {"error": f"Error parsing guidelines index: {str(e)}"}

@mcp.resource("nccn://guidelines-index")
async def get_guidelines_index() -> str:
    """
    Provides access to the NCCN guidelines index containing all available guidelines
    organized by category with their corresponding URLs.
    """
    guidelines_data = load_guidelines_index()
    if "error" in guidelines_data:
        return f"Error loading guidelines: {guidelines_data['error']}"
    
    # Format the guidelines data for easy reading
    result = ["NCCN Guidelines Index", "=" * 20, ""]
    
    if "nccn_guidelines" in guidelines_data:
        for category_data in guidelines_data["nccn_guidelines"]:
            category = category_data.get("category", "Unknown Category")
            guidelines = category_data.get("guidelines", [])
            
            result.append(f"Category: {category}")
            result.append("-" * (len(category) + 10))
            
            for guideline in guidelines:
                title = guideline.get("title", "Unknown Title")
                url = guideline.get("url", "No URL")
                result.append(f"  • {title}")
                result.append(f"    URL: {url}")
            
            result.append("")
    
    return "\n".join(result)

@mcp.tool()
async def get_index() -> str:
    """
    Get the raw contents of the NCCN guidelines index YAML file.
    
    Returns:
        String containing the raw YAML content of the guidelines index
    """
    try:
        index_path = current_dir / GUIDELINES_INDEX_FILE
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Error: Guidelines index file not found"
    except Exception as e:
        return f"Error reading guidelines index: {str(e)}"

@mcp.tool()
async def download_pdf(url: str) -> str:
    """
    Download a PDF file from the specified URL, with optional NCCN login credentials.
    
    Args:
        url: The URL of the PDF file to download
        filename: Optional custom filename for the downloaded file
        username: Optional NCCN username/email for authentication (defaults to NCCN_USERNAME env var)
        password: Optional NCCN password for authentication (defaults to NCCN_PASSWORD env var)
    
    Returns:
        String indicating success/failure and the path to the downloaded file
    """
    try:
        # Ensure download directory exists
        download_path = current_dir / DOWNLOAD_DIR
        download_path.mkdir(exist_ok=True)
        
        # Use provided credentials or fall back to global configuration
        auth_username = NCCN_USERNAME
        auth_password = NCCN_PASSWORD
        
        # Create downloader instance with credentials if available
        if auth_username and auth_password:
            downloader_instance = NCCNDownloader(auth_username, auth_password)
            print(f"Using NCCN authentication for user: {auth_username}")
        else:
            downloader_instance = downloader
            print("No NCCN authentication configured - attempting anonymous download")
        
        # Download the PDF
        success, actual_filename = downloader_instance.download_pdf(
            pdf_url=url,
            download_dir=str(download_path),
            username=auth_username,
            password=auth_password,
            skip_if_exists=True
        )
        
        # Update the full path with the actual filename used
        actual_full_path = download_path / actual_filename
        
        if success:
            return f"PDF downloaded successfully: {actual_full_path} (filename: {actual_filename})"
        else:
            error_msg = f"Failed to download PDF from {url} (attempted filename: {actual_filename})."
            if not (auth_username and auth_password):
                error_msg += " You may need to provide NCCN login credentials via environment variables (NCCN_USERNAME, NCCN_PASSWORD) or function parameters."
            return error_msg
    
    except Exception as e:
        return f"Error downloading PDF: {str(e)}"

@mcp.tool()
async def extract_content(pdf_path: str, pages: Optional[str] = None) -> str:
    """
    Extract content from specific pages of a PDF file.
    
    Args:
        pdf_path: Path to the PDF file (relative to the downloads directory or absolute path)
        pages: Comma-separated page numbers to extract (e.g., "1,3,5-7"). 
               If not specified, extracts all pages. Supports negative indexing (-1 for last page).
    
    Returns:
        Extracted text content from the specified pages
    """
    try:
        # Resolve PDF path
        if not os.path.isabs(pdf_path):
            # Try relative to downloads directory first
            download_path = current_dir / DOWNLOAD_DIR / pdf_path
            if download_path.exists():
                pdf_path = str(download_path)
            else:
                # Try relative to current directory
                current_path = current_dir / pdf_path
                if current_path.exists():
                    pdf_path = str(current_path)
                else:
                    return f"PDF file not found: {pdf_path}"
        
        # Extract content using PDFReader
        content = pdf_reader.extract_content(pdf_path, pages)
        
        if not content.strip():
            return f"No content extracted from {pdf_path} (pages: {pages or 'all'})"
        
        return content
    
    except Exception as e:
        return f"Error extracting content from PDF: {str(e)}"

def run_initialization():
    """Run the async initialization in a synchronous context."""
    try:
        asyncio.run(initialize_server())
    except Exception as e:
        print(f"Error during initialization: {e}")

if __name__ == "__main__":
    # Initialize the server first
    run_initialization()
    
    # Then run the MCP server
    mcp.run(transport='stdio')
