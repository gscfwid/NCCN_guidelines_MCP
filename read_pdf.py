from pypdf import PdfReader
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
    """PDF content reader using pypdf to preserve layout and extract internal links"""
    
    def __init__(self):
        self.xref_to_page_mapping = {}  # xref编号到页码的映射
        self.named_destinations_mapping = {}  # 对象编号到页码编号的映射
        self.reader = None

    def build_xref_to_page_mapping(self, reader):
        """构建xref编号到页码的映射关系"""
        self.xref_to_page_mapping = {}
        num_pages = len(reader.pages)
        
        for page_num in range(num_pages):
            page = reader.pages[page_num]
            xref = page.get_object().indirect_reference.idnum
            self.xref_to_page_mapping[xref] = page_num + 1  # 存储1基页码
        
        logger.info(f"Built xref to page mapping for {num_pages} pages")

    def build_named_destinations_mapping(self, reader):
        """构建named_destinations对象编号到页码编号的映射关系"""
        self.named_destinations_mapping = {}
        
        try:
            if hasattr(reader, 'named_destinations'):
                for name, dest in reader.named_destinations.items():
                    # dest通常是一个页面对象引用
                    if hasattr(dest, 'page') and hasattr(dest.page, 'idnum'):
                        page_xref = dest.page.idnum
                        # 从xref映射中找到对应的页码
                        page_num = self.xref_to_page_mapping.get(page_xref)
                        if page_num:
                            self.named_destinations_mapping[name] = page_num
                            logger.debug(f"Named destination '{name}' -> xref {page_xref} -> page {page_num}")
                
                logger.info(f"Built named destinations mapping for {len(self.named_destinations_mapping)} destinations")
        except Exception as e:
            logger.warning(f"Failed to build named destinations mapping: {e}")

    def extract_internal_links(self, page, page_num: int) -> List[Dict[str, Any]]:
        """提取页面上的内部跳转链接"""
        links = []
        
        try:
            # 在PyPDF2中，需要检查页面对象是否有annotations
            if '/Annots' in page:
                annotations = page['/Annots']
                if annotations:
                    for annot_ref in annotations:
                        try:
                            # 解析annotation对象
                            annot = annot_ref.get_object()
                            if '/A' in annot and annot['/A'] and '/S' in annot['/A']:
                                if annot['/A']['/S'] == "/GoTo":
                                    target = str(annot['/A']['/D'])
                                    target_page = None
                                    
                                    # 首先尝试从named_destinations映射中查找
                                    if target in self.named_destinations_mapping:
                                        target_page = self.named_destinations_mapping[target]
                                    else:
                                        # 处理不同类型的目标引用
                                        if "indd:" in target:
                                            # 提取indd:后面的数字部分
                                            target_parts = target.split("indd:")[1]
                                            # 可能包含多个部分，取最后一个数字
                                            import re
                                            numbers = re.findall(r'\d+', target_parts)
                                            if numbers:
                                                try:
                                                    xref_num = int(numbers[-1])  # 取最后一个数字
                                                    target_page = self.xref_to_page_mapping.get(xref_num)
                                                except ValueError:
                                                    pass
                                        else:
                                            # 尝试直接解析为数字引用
                                            import re
                                            numbers = re.findall(r'\d+', target)
                                            if numbers:
                                                try:
                                                    xref_num = int(numbers[0])
                                                    target_page = self.xref_to_page_mapping.get(xref_num)
                                                except ValueError:
                                                    pass
                                    
                                    link_info = {
                                        'source_page': page_num + 1,
                                        'target': target,
                                        'target_page': target_page
                                    }
                                    links.append(link_info)
                        except Exception as e:
                            logger.debug(f"Error processing annotation on page {page_num + 1}: {e}")
                            continue
        except Exception as e:
            logger.debug(f"No annotations found on page {page_num + 1}: {e}")
        
        return links

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
        """Extract text from page while preserving layout using pypdf"""
        try:
            # 使用pypdf的layout模式提取文本，尽量保持原始布局
            text = page.extract_text(extraction_mode="layout")
            return text if text else ""
        except Exception as e:
            logger.debug(f"Error extracting text with layout: {e}")
            # 如果layout模式失败，使用默认模式
            try:
                text = page.extract_text()
                return text if text else ""
            except Exception as e2:
                logger.warning(f"Failed to extract text from page: {e2}")
                return ""

    def extract_page_content(self, page, page_num: int) -> Dict[str, Any]:
        """Extract complete content from single page including internal links"""
        content = {
            'page_number': page_num + 1,
            'text': '',
            'internal_links': []
        }
        
        # Extract text
        content['text'] = self.extract_text_with_layout(page)
        
        # Extract internal links
        content['internal_links'] = self.extract_internal_links(page, page_num)
        
        return content

    def format_page_content(self, content: Dict[str, Any]) -> str:
        """Format page content as string including internal links"""
        result = [f"Page {content['page_number']}:"]
        
        # Add text content
        if content['text']:
            result.append(content['text'])
        
        # Add internal links content
        if content['internal_links']:
            result.append("\nInternal Links:")
            result.append("-" * 40)
            for i, link in enumerate(content['internal_links']):
                # 清理目标链接，去掉重复的前缀
                target = link['target']
                if 'indd:' in target:
                    # 找到indd:的位置，保留indd:之后的内容
                    indd_index = target.find('indd:')
                    target = target[indd_index + 5:]  # 跳过'indd:'
                    
                    # 进一步清理，去掉对象编号（冒号后面的数字）
                    if ':' in target:
                        target = target.split(':')[0]
                
                link_text = f"Link {i+1}: {target}"
                if link['target_page']:
                    link_text += f" -> Page {link['target_page']}"
                result.append(link_text)
            result.append("")
        
        return '\n'.join(result)

    def extract_content(self, pdf_path: str, pages: Optional[str] = None) -> str:
        """Main method for extracting PDF content with internal links"""
        if not pdf_path:
            raise ValueError("PDF path cannot be empty")

        try:
            logger.info(f"Starting PDF content extraction from: {pdf_path}")
            
            # Open PDF with pypdf
            self.reader = PdfReader(pdf_path)
            total_pages = len(self.reader.pages)
            
            # Build xref to page mapping
            self.build_xref_to_page_mapping(self.reader)
            
            # Build named destinations mapping
            self.build_named_destinations_mapping(self.reader)
            
            selected_pages = self.parse_pages(pages, total_pages)
            
            logger.info(f"PDF has {total_pages} pages, extracting pages: {[p+1 for p in selected_pages]}")
            
            extracted_contents = []
            
            for page_num in selected_pages:
                if page_num < len(self.reader.pages):
                    page = self.reader.pages[page_num]
                    content = self.extract_page_content(page, page_num)
                    formatted_content = self.format_page_content(content)
                    extracted_contents.append(formatted_content)
                    logger.debug(f"Extracted content from page {page_num + 1}")
            
            logger.info(f"Successfully extracted content from {len(extracted_contents)} pages")
            return "\n\n".join(extracted_contents)
                
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {str(e)}")
            raise ValueError(f"Failed to extract PDF content: {str(e)}")
