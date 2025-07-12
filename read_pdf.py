import pdfplumber
import logging
import os
from typing import List, Optional, Dict, Any

# Ensure logs directory exists
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Configure logging for this module specifically
logger = logging.getLogger(__name__)

# Only configure handlers if they haven't been added yet
if not logger.handlers:
    logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'read_pdf.log'))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False


class PDFReader:
    """PDF content reader using pdfplumber to preserve layout"""
    
    def __init__(self):
        pass

    def parse_pages(self, pages_str: Optional[str], total_pages: int) -> List[int]:
        """Parse page number string, supports single page numbers and ranges (e.g., 1,3,5-7)"""
        if not pages_str:
            return list(range(total_pages))
        
        pages = []
        for part in pages_str.split(','):
            part = part.strip()
            if not part:
                continue
            
            try:
                # Check if it's a page range (e.g., "1-5")
                if '-' in part:
                    start_str, end_str = part.split('-', 1)
                    start_page = int(start_str.strip())
                    end_page = int(end_str.strip())
                    
                    # Handle negative indexing
                    if start_page < 0:
                        start_page = total_pages + start_page + 1
                    if end_page < 0:
                        end_page = total_pages + end_page + 1
                    
                    # Ensure range is valid
                    if start_page <= 0 or end_page <= 0:
                        continue
                    if start_page > end_page:
                        start_page, end_page = end_page, start_page
                    
                    # Add all page numbers in range (convert to 0-based index)
                    for page_num in range(start_page, end_page + 1):
                        if 1 <= page_num <= total_pages:
                            pages.append(page_num - 1)  # Convert to 0-based index
                else:
                    # Single page number
                    page_num = int(part)
                    if page_num < 0:
                        page_num = total_pages + page_num + 1
                    elif page_num <= 0:
                        continue  # Skip invalid page numbers
                    
                    if 1 <= page_num <= total_pages:
                        pages.append(page_num - 1)  # Convert to 0-based index
                        
            except ValueError:
                # Skip unparseable parts
                logger.warning(f"Could not parse page specification: {part}")
                continue
                
        return sorted(set(pages))

    def extract_text_with_layout(self, page) -> str:
        """Extract text from page while preserving layout"""
        # Extract text with layout preservation
        text = page.extract_text(layout=True)
        if text:
            return text
        
        # If layout=True returns no content, try position-based sorting method
        text_objects = page.extract_words()
        if not text_objects:
            return ""
        
        # Sort by Y coordinate to simulate reading order
        sorted_objects = sorted(text_objects, key=lambda x: (-x['top'], x['x0']))
        
        lines = []
        current_line = []
        current_y = None
        tolerance = 5  # Y coordinate tolerance
        
        for obj in sorted_objects:
            if current_y is None or abs(obj['top'] - current_y) > tolerance:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                current_y = obj['top']
            current_line.append(obj['text'])
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)

    def extract_tables_from_page(self, page) -> List[List[List[str]]]:
        """Extract tables from page"""
        tables = page.extract_tables()
        return tables if tables else []

    def extract_page_content(self, page, page_num: int) -> Dict[str, Any]:
        """Extract complete content from single page"""
        content = {
            'page_number': page_num + 1,
            'text': '',
            'tables': []
        }
        
        # Extract text
        content['text'] = self.extract_text_with_layout(page)
        
        # Extract tables
        content['tables'] = self.extract_tables_from_page(page)
        
        return content

    def format_page_content(self, content: Dict[str, Any]) -> str:
        """Format page content as string"""
        result = [f"Page {content['page_number']}:"]
        
        # Add text content
        if content['text']:
            result.append(content['text'])
        
        # Add table content
        if content['tables']:
            result.append("\nTable Content:")
            result.append("-" * 40)
            for i, table in enumerate(content['tables']):
                result.append(f"Table {i+1}:")
                for row in table:
                    if row:  # Skip empty rows
                        result.append('\t'.join(str(cell) if cell else '' for cell in row))
                result.append("")
        
        return '\n'.join(result)

    def extract_content(self, pdf_path: str, pages: Optional[str] = None) -> str:
        """Main method for extracting PDF content"""
        if not pdf_path:
            raise ValueError("PDF path cannot be empty")

        try:
            logger.info(f"Starting PDF content extraction from: {pdf_path}")
            
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                selected_pages = self.parse_pages(pages, total_pages)
                
                logger.info(f"PDF has {total_pages} pages, extracting pages: {[p+1 for p in selected_pages]}")
                
                extracted_contents = []
                
                for page_num in selected_pages:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        content = self.extract_page_content(page, page_num)
                        formatted_content = self.format_page_content(content)
                        extracted_contents.append(formatted_content)
                        logger.debug(f"Extracted content from page {page_num + 1}")
                
                logger.info(f"Successfully extracted content from {len(extracted_contents)} pages")
                return "\n\n".join(extracted_contents)
                
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {str(e)}")
            raise ValueError(f"Failed to extract PDF content: {str(e)}")

    # def extract_content_structured(self, pdf_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
    #     """Extract PDF content and return structured data"""
    #     if not pdf_path:
    #         raise ValueError("PDF path cannot be empty")

    #     try:
    #         with pdfplumber.open(pdf_path) as pdf:
    #             total_pages = len(pdf.pages)
    #             selected_pages = self.parse_pages(pages, total_pages)
                
    #             contents = []
                
    #             for page_num in selected_pages:
    #                 if page_num < len(pdf.pages):
    #                     page = pdf.pages[page_num]
    #                     content = self.extract_page_content(page, page_num)
    #                     contents.append(content)
                
    #             return contents
                
    #     except Exception as e:
    #         raise ValueError(f"Failed to extract PDF content: {str(e)}")
