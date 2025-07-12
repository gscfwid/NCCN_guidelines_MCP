#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCCN自动登录和PDF下载工具
用于自动登录NCCN网站并下载指定的PDF文件
"""

import requests
from bs4 import BeautifulSoup
import os
import time

class NCCNDownloader:
    def __init__(self, username=None, password=None):
        """
        初始化NCCN下载器
        
        Args:
            username (str, optional): 用户名(邮箱)
            password (str, optional): 密码
        """
        self.session = requests.Session()
        self.username = username
        self.password = password
        # 设置请求头，模拟浏览器访问
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def login(self, username, password, target_url="https://www.nccn.org/professionals/physician_gls/pdf/gastric.pdf"):
        """
        登录NCCN网站
        
        Args:
            username (str): 用户名(邮箱)
            password (str): 密码
            target_url (str): 要访问的目标URL
        
        Returns:
            bool: 登录是否成功
        """
        try:
            print("正在访问登录页面...")
            
            # 首先访问目标URL，会被重定向到登录页面
            login_response = self.session.get(target_url)
            
            if login_response.status_code != 200:
                print(f"访问登录页面失败，状态码: {login_response.status_code}")
                return False
            
            # 解析登录页面
            soup = BeautifulSoup(login_response.text, 'html.parser')
            
            # 查找登录表单
            form = soup.find('form', {'action': '/login/Index/'})
            if not form:
                print("未找到登录表单")
                return False
            
            # 提取隐藏字段
            hidden_inputs = form.find_all('input', {'type': 'hidden'})
            form_data = {}
            
            for input_field in hidden_inputs:
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name:
                    form_data[name] = value
            
            # 添加登录凭据
            form_data.update({
                'Username': username,
                'Password': password,
                'RememberMe': 'false',  # 默认不记住
            })
            
            print("正在提交登录信息...")
            
            # 提交登录表单
            login_url = "https://www.nccn.org/login/Index/"
            
            # 设置登录请求的特定头部
            login_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_response.url,
                'Origin': 'https://www.nccn.org',
            }
            
            login_result = self.session.post(
                login_url,
                data=form_data,
                headers=login_headers,
                allow_redirects=True
            )
            
            # 检查登录是否成功
            if login_result.status_code == 200:
                # 检查是否还在登录页面（登录失败的标志）
                if '/login' in login_result.url or 'Log in' in login_result.text:
                    print("登录失败：用户名或密码错误")
                    return False
                else:
                    print("登录成功！")
                    return True
            else:
                print(f"登录请求失败，状态码: {login_result.status_code}")
                return False
                
        except Exception as e:
            print(f"登录过程中发生错误: {str(e)}")
            return False
    
    def download_pdf(self, pdf_url, download_dir=None, username=None, password=None, skip_if_exists=True):
        """
        下载PDF文件，如果需要登录会自动进行登录
        
        Args:
            pdf_url (str): PDF文件的URL
            username (str): 用户名(邮箱)，如果未登录时需要
            password (str): 密码，如果未登录时需要
            skip_if_exists (bool): 如果文件已存在是否跳过下载，默认True
        
        Returns:
            tuple: (是否成功 (bool), 保存的文件名 (str))
        """
        try:
            # 从URL自动提取文件名
            filename = os.path.basename(pdf_url)
            if not filename or not filename.endswith('.pdf'):
                filename = 'nccn_guideline.pdf'
            save_path = os.path.join(download_dir, filename)
            
            # 检查文件是否已存在
            if skip_if_exists and os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                print(f"文件已存在，跳过下载: {save_path}")
                print(f"文件大小: {file_size} bytes")
                return True, filename
            
            print(f"正在下载PDF: {pdf_url}")
            
            # 设置PDF下载的请求头
            pdf_headers = {
                'Accept': 'application/pdf,*/*',
                'Referer': 'https://www.nccn.org/',
            }
            
            response = self.session.get(pdf_url, headers=pdf_headers, stream=True)
            
            if response.status_code == 200:
                # 检查响应是否为PDF
                content_type = response.headers.get('Content-Type', '')
                if 'pdf' not in content_type.lower():
                    print("警告：响应内容可能不是PDF文件")
                    print(f"Content-Type: {content_type}")
                    
                    # 检查是否被重定向到登录页面
                    if 'text/html' in content_type and ('login' in response.text.lower() or 'log in' in response.text.lower()):
                        print("检测到需要登录，正在尝试自动登录...")
                        
                        # 如果提供了登录凭据，尝试登录
                        login_username = username or self.username
                        login_password = password or self.password
                        
                        if login_username and login_password:
                            if self.login(login_username, login_password, pdf_url):
                                print("登录成功，重新下载PDF...")
                                time.sleep(1)  # 等待登录状态稳定
                                return self.download_pdf(pdf_url, download_dir=download_dir, skip_if_exists=skip_if_exists)  # 递归调用，但不传递登录凭据避免无限循环
                            else:
                                print("自动登录失败")
                                return False, filename
                        else:
                            print("错误：需要登录但未提供用户名和密码")
                            return False, filename
                
                # 保存文件
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(save_path)
                print(f"PDF文件已保存到: {save_path}")
                print(f"文件大小: {file_size} bytes")
                
                return True, filename
            else:
                print(f"下载失败，状态码: {response.status_code}")
                return False, filename
                
        except Exception as e:
            print(f"下载过程中发生错误: {str(e)}")
            return False, filename
    
if __name__ == "__main__":
    downloader = NCCNDownloader(username="gscfwid@gmail.com", password="KrScNN0qCsE!*7")
    downloader.download_pdf("https://www.nccn.org/professionals/physician_gls/pdf/gastric.pdf", download_dir="/Users/laogao/opt/MCP/nccn_mcp/downloads")