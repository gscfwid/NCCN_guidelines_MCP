#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NCCN Automatic Login and PDF Downloader
Automates logging into the NCCN website and downloading specified PDF files.
"""

import httpx
from bs4 import BeautifulSoup
import os
import time
import logging

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
    file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'nccn_downloader.log'))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

class NCCNDownloader:
    def __init__(self, username=None, password=None):
        """
        Initializes the NCCN Downloader.
        
        Args:
            username (str, optional): Username (email address).
            password (str, optional): Password.
        """
        self.session = httpx.AsyncClient()
        self.username = username
        self.password = password
        # Set request headers to simulate a browser visit
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    async def login(self, username, password, target_url="https://www.nccn.org/professionals/physician_gls/pdf/gastric.pdf"):
        """
        Logs into the NCCN website.
        
        Args:
            username (str): Username (email address).
            password (str): Password.
            target_url (str): The target URL to access after login.
        
        Returns:
            bool: True if login is successful, False otherwise.
        """
        try:
            logger.info("Accessing login page...")
            
            # First, access the target URL, which will redirect to the login page
            login_response = await self.session.get(target_url, follow_redirects=True)
            
            logger.info(f"Login page response status: {login_response.status_code}")
            logger.info(f"Login page final URL: {login_response.url}")
            
            if login_response.status_code != 200:
                logger.error(f"Failed to access login page, status code: {login_response.status_code}")
                return False
            
            # Parse the login page
            soup = BeautifulSoup(login_response.text, 'html.parser')
            
            # Find the login form
            form = soup.find('form', {'action': '/login/Index/'})
            if not form:
                logger.error("Login form not found.")
                logger.debug(f"Page content preview: {login_response.text[:1000]}...")
                return False
            
            # Extract hidden fields
            hidden_inputs = form.find_all('input', {'type': 'hidden'})
            form_data = {}
            
            for input_field in hidden_inputs:
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name:
                    form_data[name] = value
            
            logger.info(f"Found {len(form_data)} hidden form fields")
            
            # Add login credentials
            form_data.update({
                'Username': username,
                'Password': password,
                'RememberMe': 'false',  # Do not remember by default
            })
            
            logger.info("Submitting login information...")
            
            # Submit the login form
            login_url = "https://www.nccn.org/login/Index/"
            
            # Set specific headers for the login request
            login_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': str(login_response.url),
                'Origin': 'https://www.nccn.org',
            }
            
            login_result = await self.session.post(
                login_url,
                data=form_data,
                headers=login_headers,
                follow_redirects=True
            )
            
            logger.info(f"Login result status: {login_result.status_code}")
            logger.info(f"Login result final URL: {login_result.url}")
            
            # Check if login was successful
            if login_result.status_code == 200:
                # Check if still on the login page (indicates login failure)
                if '/login' in str(login_result.url) or 'Log in' in login_result.text:
                    logger.error("Login failed: Incorrect username or password.")
                    return False
                else:
                    logger.info("Login successful!")
                    return True
            else:
                logger.error(f"Login request failed, status code: {login_result.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"An error occurred during login: {str(e)}")
            return False
    
    async def download_pdf(self, pdf_url, download_dir=None, username=None, password=None, skip_if_exists=True):
        """
        Downloads a PDF file, automatically logging in if required.
        
        Args:
            pdf_url (str): URL of the PDF file.
            download_dir (str, optional): Directory to save the PDF. Defaults to current directory.
            username (str, optional): Username (email address), required if not already logged in.
            password (str, optional): Password, required if not already logged in.
            skip_if_exists (bool): Whether to skip download if the file already exists. Defaults to True.
        
        Returns:
            tuple: (success (bool), saved_filename (str))
        """
        try:
            # Automatically extract filename from URL
            filename = os.path.basename(pdf_url)
            if not filename or not filename.endswith('.pdf'):
                filename = 'nccn_guideline.pdf'
            
            if download_dir:
                os.makedirs(download_dir, exist_ok=True)
            else:
                download_dir = os.getcwd() # Use current working directory if not specified
            
            save_path = os.path.join(download_dir, filename)
            
            # Check if file already exists
            if skip_if_exists and os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                logger.info(f"File already exists, skipping download: {save_path}")
                logger.info(f"File size: {file_size} bytes")
                return True, filename
            
            logger.info(f"Downloading PDF: {pdf_url}")
            
            # Set request headers for PDF download
            pdf_headers = {
                'Accept': 'application/pdf,*/*',
                'Referer': 'https://www.nccn.org/',
            }
            
            # First, make a regular GET request to check the response
            response = await self.session.get(pdf_url, headers=pdf_headers, follow_redirects=True)
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Final URL: {response.url}")
            
            # Check if we were redirected to a login page
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                logger.info(f"Content-Type: {content_type}")
                
                # Check if this is actually a PDF
                if 'application/pdf' in content_type:
                    # This is a PDF, save it directly
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    
                    file_size = os.path.getsize(save_path)
                    logger.info(f"PDF file saved to: {save_path}")
                    logger.info(f"File size: {file_size} bytes")
                    return True, filename
                
                elif 'text/html' in content_type:
                    # This is HTML, likely a login page
                    response_text = response.text
                    
                    if 'login' in response_text.lower() or 'log in' in response_text.lower():
                        logger.info("Login required detected, attempting automatic login...")
                        
                        # If login credentials are provided, attempt to log in
                        login_username = username or self.username
                        login_password = password or self.password
                        
                        if login_username and login_password:
                            if await self.login(login_username, login_password, pdf_url):
                                logger.info("Login successful, re-downloading PDF...")
                                time.sleep(1)  # Wait for login state to stabilize
                                # Recursive call, but do not pass login credentials to avoid infinite loop
                                return await self.download_pdf(pdf_url, download_dir=download_dir, skip_if_exists=skip_if_exists)
                            else:
                                logger.error("Automatic login failed.")
                                return False, filename
                        else:
                            logger.error("Login required but username and password not provided.")
                            return False, filename
                    else:
                        logger.warning("Received HTML response but no login form detected.")
                        logger.debug(f"Response preview: {response_text[:500]}...")
                        return False, filename
                else:
                    logger.warning(f"Unexpected content type: {content_type}")
                    return False, filename
            
            elif response.status_code == 302:
                # Handle redirect manually if needed
                redirect_url = response.headers.get('Location')
                logger.info(f"Received redirect to: {redirect_url}")
                
                # Check if redirect is to login page
                if redirect_url and 'login' in redirect_url.lower():
                    logger.info("Redirected to login page, attempting automatic login...")
                    
                    login_username = username or self.username
                    login_password = password or self.password
                    
                    if login_username and login_password:
                        if await self.login(login_username, login_password, pdf_url):
                            logger.info("Login successful, re-downloading PDF...")
                            time.sleep(1)
                            return await self.download_pdf(pdf_url, download_dir=download_dir, skip_if_exists=skip_if_exists)
                        else:
                            logger.error("Automatic login failed.")
                            return False, filename
                    else:
                        logger.error("Login required but username and password not provided.")
                        return False, filename
                else:
                    logger.error(f"Unexpected redirect to: {redirect_url}")
                    return False, filename
            
            else:
                logger.error(f"Download failed, status code: {response.status_code}")
                return False, filename
                
        except Exception as e:
            logger.error(f"An error occurred during download: {str(e)}")
            return False, filename
    
    async def __aenter__(self):
        """Asynchronous context manager entry point."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asynchronous context manager exit point."""
        await self.session.aclose()

