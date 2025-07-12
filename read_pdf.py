import pdfplumber
from typing import List, Optional, Dict, Any


class PDFReader:
    """PDF内容读取器，使用pdfplumber保留布局"""
    
    def __init__(self):
        pass

    def parse_pages(self, pages_str: Optional[str], total_pages: int) -> List[int]:
        """解析页码字符串，支持单个页码和范围（如 1,3,5-7）"""
        if not pages_str:
            return list(range(total_pages))
        
        pages = []
        for part in pages_str.split(','):
            part = part.strip()
            if not part:
                continue
            
            try:
                # 检查是否是页面范围（如 "1-5"）
                if '-' in part:
                    start_str, end_str = part.split('-', 1)
                    start_page = int(start_str.strip())
                    end_page = int(end_str.strip())
                    
                    # 处理负数索引
                    if start_page < 0:
                        start_page = total_pages + start_page + 1
                    if end_page < 0:
                        end_page = total_pages + end_page + 1
                    
                    # 确保范围有效
                    if start_page <= 0 or end_page <= 0:
                        continue
                    if start_page > end_page:
                        start_page, end_page = end_page, start_page
                    
                    # 添加范围内的所有页码（转换为0索引）
                    for page_num in range(start_page, end_page + 1):
                        if 1 <= page_num <= total_pages:
                            pages.append(page_num - 1)  # 转换为0索引
                else:
                    # 单个页码
                    page_num = int(part)
                    if page_num < 0:
                        page_num = total_pages + page_num + 1
                    elif page_num <= 0:
                        continue  # 跳过无效页码
                    
                    if 1 <= page_num <= total_pages:
                        pages.append(page_num - 1)  # 转换为0索引
                        
            except ValueError:
                # 跳过无法解析的部分
                continue
                
        return sorted(set(pages))

    def extract_text_with_layout(self, page) -> str:
        """从页面提取文本并保持布局"""
        # 提取文本，保持布局
        text = page.extract_text(layout=True)
        if text:
            return text
        
        # 如果layout=True没有内容，尝试按位置排序的方法
        text_objects = page.extract_words()
        if not text_objects:
            return ""
        
        # 按Y坐标排序，模拟阅读顺序
        sorted_objects = sorted(text_objects, key=lambda x: (-x['top'], x['x0']))
        
        lines = []
        current_line = []
        current_y = None
        tolerance = 5  # Y坐标容差
        
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
        """从页面提取表格"""
        tables = page.extract_tables()
        return tables if tables else []

    def extract_page_content(self, page, page_num: int) -> Dict[str, Any]:
        """提取单页的完整内容"""
        content = {
            'page_number': page_num + 1,
            'text': '',
            'tables': []
        }
        
        # 提取文本
        content['text'] = self.extract_text_with_layout(page)
        
        # 提取表格
        content['tables'] = self.extract_tables_from_page(page)
        
        return content

    def format_page_content(self, content: Dict[str, Any]) -> str:
        """格式化页面内容为字符串"""
        result = [f"Page {content['page_number']}:"]
        
        # 添加文本内容
        if content['text']:
            result.append(content['text'])
        
        # 添加表格内容
        if content['tables']:
            result.append("\n表格内容:")
            result.append("-" * 40)
            for i, table in enumerate(content['tables']):
                result.append(f"表格 {i+1}:")
                for row in table:
                    if row:  # 跳过空行
                        result.append('\t'.join(str(cell) if cell else '' for cell in row))
                result.append("")
        
        return '\n'.join(result)

    def extract_content(self, pdf_path: str, pages: Optional[str] = None) -> str:
        """提取PDF内容的主方法"""
        if not pdf_path:
            raise ValueError("PDF路径不能为空")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                selected_pages = self.parse_pages(pages, total_pages)
                
                extracted_contents = []
                
                for page_num in selected_pages:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        content = self.extract_page_content(page, page_num)
                        formatted_content = self.format_page_content(content)
                        extracted_contents.append(formatted_content)
                
                return "\n\n".join(extracted_contents)
                
        except Exception as e:
            raise ValueError(f"提取PDF内容失败: {str(e)}")

    # def extract_content_structured(self, pdf_path: str, pages: Optional[str] = None) -> List[Dict[str, Any]]:
    #     """提取PDF内容并返回结构化数据"""
    #     if not pdf_path:
    #         raise ValueError("PDF路径不能为空")

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
    #         raise ValueError(f"提取PDF内容失败: {str(e)}")
