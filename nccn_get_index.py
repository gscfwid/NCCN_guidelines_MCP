#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCCN网站爬取器
爬取NCCN指南分类页面并生成YAML索引文档
支持智能缓存机制，适用于MCP Server自动化场景
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import yaml
import os
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 常量
DEFAULT_OUTPUT_FILE = 'nccn_guidelines_index.yaml'
CACHE_MAX_AGE_DAYS = 7  # 缓存文件默认最大有效期（天）


async def fetch_page(client: httpx.AsyncClient, url: str, max_retries: int = 3) -> str:
    """
    异步获取单个页面内容，支持重试机制
    
    Args:
        client: httpx异步客户端
        url: 要爬取的URL
        max_retries: 最大重试次数，默认3次
    
    Returns:
        页面HTML内容
    """
    import asyncio
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"获取页面失败 {url} (第{attempt + 1}次尝试): {e}, 1秒后重试...")
                await asyncio.sleep(1)  # 等待1秒后重试
            else:
                logger.error(f"获取页面最终失败 {url} (已重试{max_retries}次): {e}")
                return ""


async def get_page_title(client: httpx.AsyncClient, url: str) -> str:
    """
    获取页面标题
    
    Args:
        client: httpx异步客户端
        url: 页面URL
    
    Returns:
        页面标题
    """
    # 分类页面比较重要，使用更多重试次数
    html = await fetch_page(client, url, max_retries=5)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    return ""


async def extract_item_links(client: httpx.AsyncClient, url: str) -> list:
    """
    从页面中提取class为item-name的div中的链接和标题
    
    Args:
        client: httpx异步客户端
        url: 页面URL
    
    Returns:
        包含链接和标题的字典列表
    """
    # 分类页面比较重要，使用更多重试次数
    html = await fetch_page(client, url, max_retries=5)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    
    # 查找class为item-name的div
    item_divs = soup.find_all('div', class_='item-name')
    
    for div in item_divs:
        # 在div下查找链接元素
        link_elem = div.find('a')
        if link_elem:
            href = link_elem.get('href')
            title = link_elem.get_text(strip=True)
            
            if href and title:
                # 转换为绝对URL
                absolute_url = urljoin(url, href)
                items.append({
                    'title': title,
                    'url': absolute_url
                })
    
    return items


async def find_nccn_guideline_link(client: httpx.AsyncClient, url: str) -> str:
    """
    在第三级页面中查找内容为"NCCN guidelines"的元素的超链接
    
    Args:
        client: httpx异步客户端
        url: 第三级页面URL
    
    Returns:
        NCCN guidelines的链接，如果未找到返回空字符串
    """
    # 第三级页面数量较多，使用适中的重试次数
    html = await fetch_page(client, url, max_retries=3)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找包含"NCCN guidelines"文本的元素
    for elem in soup.find_all(['a', 'span', 'div', 'p']):
        text = elem.get_text(strip=True).lower()
        if text == "nccn guidelines":
            # 如果是链接元素，直接返回href
            if elem.name == 'a' and elem.get('href'):
                return urljoin(url, elem.get('href'))
    return ""


async def process_single_item(client: httpx.AsyncClient, item: dict) -> dict:
    """
    处理单个item，查找其NCCN guidelines链接
    
    Args:
        client: httpx异步客户端
        item: 包含title和url的字典
    
    Returns:
        增强后的item字典，包含guideline_link
    """
    guideline_link = await find_nccn_guideline_link(client, item['url'])
    return {
        'title': item['title'],
        'url': item['url'],
        'guideline_link': guideline_link
    }


async def process_category(client: httpx.AsyncClient, category_num: int) -> dict:
    """
    处理单个分类页面
    
    Args:
        client: httpx异步客户端
        category_num: 分类编号(1-4)
    
    Returns:
        包含分类信息和子项的字典
    """
    category_url = f"https://www.nccn.org/guidelines/category_{category_num}"
    logger.info(f"处理分类页面: {category_url}")
    
    # 获取页面标题
    title = await get_page_title(client, category_url)
    
    # 获取页面中的item链接
    items = await extract_item_links(client, category_url)
    
    if not items:
        logger.warning(f"分类 {category_num} 未找到任何items")
        return {
            'category_num': category_num,
            'title': title,
            'url': category_url,
            'items': []
        }
    
    logger.info(f"分类 {category_num} 找到 {len(items)} 个items，开始并发处理第三级页面...")
    
    # 并发处理所有第三级页面
    tasks = [process_single_item(client, item) for item in items]
    enhanced_items = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 过滤掉异常结果，保留有效结果
    valid_items = []
    for i, result in enumerate(enhanced_items):
        if isinstance(result, Exception):
            logger.error(f"处理item失败 {items[i]['url']}: {result}")
            # 即使失败也保留原始信息
            valid_items.append({
                'title': items[i]['title'],
                'url': items[i]['url'],
                'guideline_link': ''
            })
        else:
            valid_items.append(result)
    
    logger.info(f"分类 {category_num} 第三级页面处理完成")
    
    return {
        'category_num': category_num,
        'title': title,
        'url': category_url,
        'items': valid_items
    }


async def scrape_all_categories() -> list:
    """
    爬取所有分类页面
    
    Returns:
        所有分类的数据列表
    """
    async with httpx.AsyncClient(
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),  # 设置连接和读取超时
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)  # 限制连接数
    ) as client:
        
        # 并发处理4个分类页面
        tasks = [process_category(client, i) for i in range(1, 5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤掉异常结果
        valid_results = [r for r in results if not isinstance(r, Exception)]
        
        return valid_results


def generate_yaml(categories_data: list) -> str:
    """
    生成YAML格式的指南索引
    
    Args:
        categories_data: 分类数据列表
    
    Returns:
        YAML格式的文档字符串
    """
    # 构建层级化的数据结构
    categories = []
    
    for category in categories_data:
        category_title = category.get('title', f'Category {category["category_num"]}')
        
        # 收集该分类下的所有有效指南
        guidelines = []
        for item in category.get('items', []):
            # 只保留有guideline_link的项目
            if item.get('guideline_link'):
                guidelines.append({
                    'title': item['title'],
                    'url': item['guideline_link']
                })
        
        # 只有当有有效指南时才添加该分类
        if guidelines:
            categories.append({
                'category': category_title,
                'guidelines': guidelines
            })
    
    # 转换为YAML格式
    yaml_data = {
        'nccn_guidelines': categories
    }
    
    return yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def check_cache_file(output_file: str = DEFAULT_OUTPUT_FILE) -> dict:
    """
    检查缓存文件的状态
    
    Args:
        output_file: 输出文件路径
    
    Returns:
        包含缓存文件信息的字典
    """
    cache_info = {
        'exists': False,
        'file_path': output_file,
        'size': 0,
        'created_time': None,
        'age_days': 0,
        'is_valid': False
    }
    
    if os.path.exists(output_file):
        cache_info['exists'] = True
        stat = os.stat(output_file)
        cache_info['size'] = stat.st_size
        cache_info['created_time'] = datetime.fromtimestamp(stat.st_mtime)
        
        # 计算文件年龄
        age_delta = datetime.now() - cache_info['created_time']
        cache_info['age_days'] = age_delta.days
        
        # 判断是否在有效期内且文件不为空
        cache_info['is_valid'] = cache_info['age_days'] < CACHE_MAX_AGE_DAYS and cache_info['size'] > 0
    
    return cache_info


def load_cached_data(output_file: str = DEFAULT_OUTPUT_FILE) -> dict:
    """
    加载缓存的YAML数据
    
    Args:
        output_file: 输出文件路径
    
    Returns:
        解析后的YAML数据，如果失败返回空字典
    """
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"读取缓存文件失败: {e}")
        return {}


async def ensure_nccn_index(output_file: str = DEFAULT_OUTPUT_FILE, max_age_days: int = CACHE_MAX_AGE_DAYS) -> dict:
    """
    确保NCCN指南索引存在且有效
    这是MCP Server的主要调用接口
    
    Args:
        output_file: 输出文件路径
        max_age_days: 缓存文件最大有效期(天)
    
    Returns:
        解析后的指南索引数据
    """
    import time
    
    # 检查缓存文件
    cache_info = check_cache_file(output_file)
    
    # 判断是否需要重新爬取
    should_scrape = not cache_info['exists'] or not cache_info['is_valid']
    
    if cache_info['exists']:
        if cache_info['is_valid']:
            logger.info(f"使用有效缓存文件: {output_file} (创建于 {cache_info['created_time'].strftime('%Y-%m-%d %H:%M:%S')}, {cache_info['age_days']}天前)")
        else:
            logger.info(f"缓存文件已过期 ({cache_info['age_days']}天 > {max_age_days}天) 或异常，开始重新爬取...")
    else:
        logger.info("未找到缓存文件，开始爬取NCCN指南索引...")
    
    if should_scrape:
        start_time = time.time()
        
        try:
            # 爬取所有分类数据
            categories_data = await scrape_all_categories()
            
            if not categories_data:
                logger.error("爬取失败，未获取到任何数据")
                # 如果爬取失败但有旧缓存，尝试使用旧缓存
                if cache_info['exists']:
                    logger.info("爬取失败，尝试使用现有缓存文件")
                    return load_cached_data(output_file)
                return {}
            
            # 生成YAML文档
            yaml_content = generate_yaml(categories_data)
            
            # 保存到文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            # 计算统计信息
            total_guidelines = sum(len(cat.get('items', [])) for cat in categories_data)
            successful_guidelines = sum(
                len([item for item in cat.get('items', []) if item.get('guideline_link')])
                for cat in categories_data
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(f"爬取完成！索引已保存到 {output_file}")
            logger.info(f"处理了 {len(categories_data)} 个分类，找到 {successful_guidelines}/{total_guidelines} 个有效指南链接")
            logger.info(f"爬取耗时: {elapsed_time:.2f} 秒")
            
        except Exception as e:
            logger.error(f"爬取过程出错: {e}")
            # 如果爬取失败但有缓存，使用缓存
            if cache_info['exists']:
                logger.info("爬取失败，使用现有缓存文件")
                return load_cached_data(output_file)
            return {}
    
    # 加载并返回数据
    cached_data = load_cached_data(output_file)
    if cached_data and 'nccn_guidelines' in cached_data:
        total_categories = len(cached_data['nccn_guidelines'])
        total_guidelines = sum(len(cat.get('guidelines', [])) for cat in cached_data['nccn_guidelines'])
        logger.info(f"NCCN指南索引就绪: {total_categories} 个分类，共 {total_guidelines} 个指南")
    else:
        logger.warning("指南索引文件格式异常")
    
    return cached_data


async def main():
    """
    主函数 - 用于直接运行脚本测试
    """
    result = await ensure_nccn_index()
    if result:
        logger.info("指南索引获取成功")
    else:
        logger.error("指南索引获取失败")


if __name__ == "__main__":
    asyncio.run(main()) 