#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCCN Website Scraper
Scrapes NCCN guideline category pages and generates YAML index documents
Supports intelligent caching mechanism for MCP Server automation scenarios
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import yaml
import os
from datetime import datetime

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
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'nccn_get_index.log'))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

# Constants
DEFAULT_OUTPUT_FILE = 'nccn_guidelines_index.yaml'
CACHE_MAX_AGE_DAYS = 7  # Default maximum cache file validity period (days)


async def fetch_page(client: httpx.AsyncClient, url: str, max_retries: int = 3) -> str:
    """
    Asynchronously fetch single page content with retry mechanism
    
    Args:
        client: httpx async client
        url: URL to scrape
        max_retries: Maximum retry attempts, default 3
    
    Returns:
        Page HTML content
    """
    import asyncio
    
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Failed to fetch page {url} (attempt {attempt + 1}): {e}, retrying in 1 second...")
                await asyncio.sleep(1)  # Wait 1 second before retry
            else:
                logger.error(f"Final failure to fetch page {url} (after {max_retries} retries): {e}")
                return ""


async def get_page_title(client: httpx.AsyncClient, url: str) -> str:
    """
    Get page title
    
    Args:
        client: httpx async client
        url: Page URL
    
    Returns:
        Page title
    """
    # Category pages are important
    html = await fetch_page(client, url, max_retries=3)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    return ""


async def extract_item_links(client: httpx.AsyncClient, url: str) -> list:
    """
    Extract links and titles from div elements with class 'item-name' on the page
    
    Args:
        client: httpx async client
        url: Page URL
    
    Returns:
        List of dictionaries containing links and titles
    """
    # Category pages are important, use more retries
    html = await fetch_page(client, url, max_retries=5)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    
    # Find div elements with class 'item-name'
    item_divs = soup.find_all('div', class_='item-name')
    
    for div in item_divs:
        # Find link elements under the div
        link_elem = div.find('a')
        if link_elem:
            href = link_elem.get('href')
            title = link_elem.get_text(strip=True)
            
            if href and title:
                # Convert to absolute URL
                absolute_url = urljoin(url, href)
                items.append({
                    'title': title,
                    'url': absolute_url
                })
    
    return items


async def find_nccn_guideline_link(client: httpx.AsyncClient, url: str) -> str:
    """
    Find hyperlink of element containing 'NCCN guidelines' text on third-level page
    
    Args:
        client: httpx async client
        url: Third-level page URL
    
    Returns:
        NCCN guidelines link, returns empty string if not found
    """
    # Third-level pages are numerous
    html = await fetch_page(client, url, max_retries=3)
    if not html:
        return ""
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find elements containing 'NCCN guidelines' text
    for elem in soup.find_all(['a', 'span', 'div', 'p']):
        text = elem.get_text(strip=True).lower()
        if text == "nccn guidelines":
            # If it's a link element, return href directly
            if elem.name == 'a' and elem.get('href'):
                return urljoin(url, elem.get('href'))
    return ""


async def process_single_item(client: httpx.AsyncClient, item: dict) -> dict:
    """
    Process single item, find its NCCN guidelines link
    
    Args:
        client: httpx async client
        item: Dictionary containing title and url
    
    Returns:
        Enhanced item dictionary containing guideline_link
    """
    guideline_link = await find_nccn_guideline_link(client, item['url'])
    return {
        'title': item['title'],
        'url': item['url'],
        'guideline_link': guideline_link
    }


async def process_category(client: httpx.AsyncClient, category_num: int) -> dict:
    """
    Process single category page
    
    Args:
        client: httpx async client
        category_num: Category number (1-4)
    
    Returns:
        Dictionary containing category information and sub-items
    """
    category_url = f"https://www.nccn.org/guidelines/category_{category_num}"
    logger.info(f"Processing category page: {category_url}")
    
    # Get page title
    title = await get_page_title(client, category_url)
    
    # Get item links from page
    items = await extract_item_links(client, category_url)
    
    if not items:
        logger.warning(f"Category {category_num} found no items")
        return {
            'category_num': category_num,
            'title': title,
            'url': category_url,
            'items': []
        }
    
    logger.info(f"Category {category_num} found {len(items)} items, starting concurrent processing of third-level pages...")
    
    # Process all third-level pages concurrently
    tasks = [process_single_item(client, item) for item in items]
    enhanced_items = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exception results, keep valid results
    valid_items = []
    for i, result in enumerate(enhanced_items):
        if isinstance(result, Exception):
            logger.error(f"Failed to process item {items[i]['url']}: {result}")
            # Keep original information even if failed
            valid_items.append({
                'title': items[i]['title'],
                'url': items[i]['url'],
                'guideline_link': ''
            })
        else:
            valid_items.append(result)
    
    logger.info(f"Category {category_num} third-level page processing completed")
    
    return {
        'category_num': category_num,
        'title': title,
        'url': category_url,
        'items': valid_items
    }


async def scrape_all_categories() -> list:
    """
    Scrape all category pages
    
    Returns:
        List of all category data
    """
    async with httpx.AsyncClient(
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),  # Set connection and read timeout
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)  # Limit connections
    ) as client:
        
        # Process 4 category pages concurrently
        tasks = [process_category(client, i) for i in range(1, 5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exception results
        valid_results = [r for r in results if not isinstance(r, Exception)]
        
        return valid_results


def generate_yaml(categories_data: list) -> str:
    """
    Generate YAML format guideline index
    
    Args:
        categories_data: List of category data
    
    Returns:
        YAML format document string
    """
    # Build hierarchical data structure
    categories = []
    
    for category in categories_data:
        category_title = category.get('title', f'Category {category["category_num"]}')
        
        # Collect all valid guidelines under this category
        guidelines = []
        for item in category.get('items', []):
            # Only keep items with guideline_link
            if item.get('guideline_link'):
                guidelines.append({
                    'title': item['title'],
                    'url': item['guideline_link']
                })
        
        # Only add category if it has valid guidelines
        if guidelines:
            categories.append({
                'category': category_title,
                'guidelines': guidelines
            })
    
    # Convert to YAML format
    yaml_data = {
        'nccn_guidelines': categories
    }
    
    return yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True, sort_keys=False)


def check_cache_file(output_file: str = DEFAULT_OUTPUT_FILE) -> dict:
    """
    Check cache file status
    
    Args:
        output_file: Output file path
    
    Returns:
        Dictionary containing cache file information
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
        
        # Calculate file age
        age_delta = datetime.now() - cache_info['created_time']
        cache_info['age_days'] = age_delta.days
        
        # Check if within validity period and file is not empty
        cache_info['is_valid'] = cache_info['age_days'] < CACHE_MAX_AGE_DAYS and cache_info['size'] > 0
    
    return cache_info


def load_cached_data(output_file: str = DEFAULT_OUTPUT_FILE) -> dict:
    """
    Load cached YAML data
    
    Args:
        output_file: Output file path
    
    Returns:
        Parsed YAML data, returns empty dict if failed
    """
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read cache file: {e}")
        return {}


async def ensure_nccn_index(output_file: str = DEFAULT_OUTPUT_FILE, max_age_days: int = CACHE_MAX_AGE_DAYS) -> dict:
    """
    Ensure NCCN guideline index exists and is valid
    This is the main interface for MCP Server calls
    
    Args:
        output_file: Output file path
        max_age_days: Maximum cache file validity period (days)
    
    Returns:
        Parsed guideline index data
    """
    import time
    
    # Check cache file
    cache_info = check_cache_file(output_file)
    
    # Determine if re-scraping is needed
    should_scrape = not cache_info['exists'] or not cache_info['is_valid']
    
    if cache_info['exists']:
        if cache_info['is_valid']:
            logger.info(f"Using valid cache file: {output_file} (created at {cache_info['created_time'].strftime('%Y-%m-%d %H:%M:%S')}, {cache_info['age_days']} days ago)")
        else:
            logger.info(f"Cache file expired ({cache_info['age_days']} days > {max_age_days} days) or corrupted, starting re-scraping...")
    else:
        logger.info("Cache file not found, starting NCCN guideline index scraping...")
    
    if should_scrape:
        start_time = time.time()
        
        try:
            # Scrape all category data
            categories_data = await scrape_all_categories()
            
            if not categories_data:
                logger.error("Scraping failed, no data retrieved")
                # If scraping fails but old cache exists, try using old cache
                if cache_info['exists']:
                    logger.info("Scraping failed, attempting to use existing cache file")
                    return load_cached_data(output_file)
                return {}
            
            # Generate YAML document
            yaml_content = generate_yaml(categories_data)
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            # Calculate statistics
            total_guidelines = sum(len(cat.get('items', [])) for cat in categories_data)
            successful_guidelines = sum(
                len([item for item in cat.get('items', []) if item.get('guideline_link')])
                for cat in categories_data
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(f"Scraping completed! Index saved to {output_file}")
            logger.info(f"Processed {len(categories_data)} categories, found {successful_guidelines}/{total_guidelines} valid guideline links")
            logger.info(f"Scraping time: {elapsed_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error during scraping process: {e}")
            # If scraping fails but cache exists, use cache
            if cache_info['exists']:
                logger.info("Scraping failed, using existing cache file")
                return load_cached_data(output_file)
            return {}
    
    # Load and return data
    cached_data = load_cached_data(output_file)
    if cached_data and 'nccn_guidelines' in cached_data:
        total_categories = len(cached_data['nccn_guidelines'])
        total_guidelines = sum(len(cat.get('guidelines', [])) for cat in cached_data['nccn_guidelines'])
        logger.info(f"NCCN guideline index ready: {total_categories} categories, {total_guidelines} total guidelines")
    else:
        logger.warning("Guideline index file format is abnormal")
    
    return cached_data


async def main():
    """
    Main function - for direct script testing
    """
    result = await ensure_nccn_index()
    if result:
        logger.info("Guideline index retrieved successfully")
    else:
        logger.error("Failed to retrieve guideline index")


if __name__ == "__main__":
    asyncio.run(main()) 