# Developed by: https://github.com/zebbern
"""Temporary Email Service APIs for TempMail Pro"""
import random
import string
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Protocol
import requests  # For synchronous APIs
import asyncio
import logging


class TempMailAPI(Protocol):
    """Protocol/Interface for all temporary email services"""
    
    async def create_address(self, domain: str = None) -> Dict:
        """Create a new email address. Returns dict with 'email' and 'token'"""
        ...
    
    async def get_messages(self, token: str) -> List[Dict]:
        """Get messages for a given token. Returns list of message dicts"""
        ...
    
    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content by ID"""
        ...
    
    @property
    def service_name(self) -> str:
        """Return service name"""
        ...
    
    @property
    def domains(self) -> List[str]:
        """Return available domains"""
        ...
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        ...


class GuerrillaMailAPI:
    """API handler for Guerrilla Mail service."""
    BASE_URL = 'https://api.guerrillamail.com/ajax.php'
    DOMAINS = ['grr.la', 'sharklasers.com', 'guerrillamail.net', 'guerrillamail.com']
    SERVICE_NAME = "Guerrilla Mail"

    def __init__(self):
        self.salt = int(datetime.now().timestamp() * 1000)

    def _default_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'TempMailPro/3.0',
            'Accept': 'application/json',
            'Referer': 'https://guerrillamail.com/'
        }

    async def create_address(self, domain: str = None) -> Dict:
        """Create a new email address."""
        if domain is None:
            domain = self.DOMAINS[0]
        
        params = {'f': 'get_email_address', 't': str(self.salt)}
        self.salt += 1
        
        async with aiohttp.ClientSession(headers=self._default_headers()) as session:
            async with session.get(self.BASE_URL, params=params) as resp:
                try:
                    data = await resp.json()
                    return {'email': data['email_addr'], 'token': data['sid_token']}
                except Exception:
                    params = {'f': 'get_email_address'}
                    async with session.get(self.BASE_URL, params=params) as fallback_resp:
                        data = await fallback_resp.json()
                        return {'email': data['email_addr'], 'token': data['sid_token']}

    async def get_messages(self, token: str) -> List[Dict]:
        params = {'f': 'get_email_list', 'sid_token': token, 'offset': '0'}
        async with aiohttp.ClientSession(headers=self._default_headers()) as session:
            async with session.get(self.BASE_URL, params=params) as resp:
                data = await resp.json()
                messages = data.get('list', [])
                
                # Normalize message format and ensure subject is properly extracted
                normalized = []
                for msg in messages:
                    normalized.append({
                        'mail_id': msg.get('mail_id', ''),
                        'subject': msg.get('mail_subject', 'No Subject'),  # Correct field for subject
                        'mail_from': msg.get('mail_from', 'Unknown'),
                        'mail_date': msg.get('mail_date', ''),
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    })
                return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch a specific message."""
        try:
            params = {'f': 'fetch_email', 'sid_token': token, 'email_id': message_id}
            async with aiohttp.ClientSession(headers=self._default_headers()) as session:
                async with session.get(self.BASE_URL, params=params) as resp:
                    data = await resp.json()
                    
                    # Get the mail body correctly from both possible locations
                    mail_body = data.get('mail_body', '')
                    if not mail_body:
                        mail_body = data.get('body', '')
                        
                    # Make sure we handle HTML bodies correctly
                    mail_body_html = data.get('body_html', '')
                    if mail_body_html and not mail_body:
                        mail_body = mail_body_html
                    
                    # Create normalized response with correct subject field
                    return {
                        'mail_body': mail_body,
                        'mail_from': data.get('mail_from', 'Unknown'),
                        'subject': data.get('mail_subject', 'No Subject'),  # Use correct field
                        'mail_date': data.get('mail_timestamp', ''),
                        'mail_size': data.get('mail_size', 0),
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    }
        except Exception as e:
            logging.error(f"GuerrillaMailAPI fetch_message error: {str(e)}")
            # Return minimal data to prevent further errors
            return {
                'mail_body': f"Error loading message: {str(e)}",
                'mail_from': 'Unknown',
                'subject': 'Error retrieving message',
                'mail_date': '',
                'mail_size': 0,
                'receive_time': datetime.now().timestamp()
            }

    @property
    def service_name(self) -> str:
        return self.SERVICE_NAME
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        return 3600  # 1 hour


class MailGwAPI:
    """API handler for Mail.gw service."""
    BASE_URL = 'https://api.mail.gw'
    SERVICE_NAME = "Mail.gw"

    def __init__(self):
        self._domains = None

    def _randstr(self, n=10):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    async def _get_domains(self) -> List[str]:
        """Fetch available domains"""
        if self._domains is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/domains") as resp:
                    data = await resp.json()
                    self._domains = [d["domain"] for d in data["hydra:member"]]
        return self._domains

    async def create_address(self, domain: str = None) -> Dict:
        """Create a new account with Mail.gw"""
        if domain is None:
            domains = await self._get_domains()
            domain = random.choice(domains)
        
        local = self._randstr()
        email = f"{local}@{domain}"
        password = self._randstr(12)
        
        async with aiohttp.ClientSession() as session:
            # Create account
            async with session.post(f"{self.BASE_URL}/accounts", 
                                     json={"address": email, "password": password}) as resp:
                await resp.json()  # Just check for errors
            
            # Get token
            async with session.post(f"{self.BASE_URL}/token",
                                     json={"address": email, "password": password}) as resp:
                data = await resp.json()
                token = data["token"]
        
        return {'email': email, 'token': token}

    async def get_messages(self, token: str) -> List[Dict]:
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/messages", headers=headers) as resp:
                data = await resp.json()
                messages = data.get("hydra:member", [])
                
                # Normalize message format
                normalized = []
                for msg in messages:
                    normalized.append({
                        'mail_id': msg['id'],
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                        'mail_date': msg.get('createdAt', ''),
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    })
                return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content for Mail.gw"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/messages/{message_id}", headers=headers) as resp:
                    msg = await resp.json()
                    
                    # Prioritize HTML content if available
                    html_content = msg.get('html', '')
                    text_content = msg.get('text', '')
                    
                    # Check if content exists at alternate locations in the response
                    if not html_content and not text_content:
                        if 'payload' in msg:
                            html_content = msg.get('payload', {}).get('html', '')
                            text_content = msg.get('payload', {}).get('text', '')
                    
                    # Ensure content is a string, not a list
                    if isinstance(html_content, list):
                        html_content = '\n'.join([str(item) for item in html_content])
                    if isinstance(text_content, list):
                        text_content = '\n'.join([str(item) for item in text_content])
                    
                    # Use HTML if available, else text
                    final_content = html_content if html_content else text_content
                    
                    # Calculate size based on content length
                    message_size = len(final_content.encode('utf-8'))
                    
                    # Format date if available
                    created_date = msg.get('createdAt', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    # Normalize message format
                    return {
                        'mail_body': final_content,
                        'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_date': created_date,
                        'mail_size': message_size,
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    }
        except Exception as e:
            logging.error(f"MailGwAPI fetch_message error: {str(e)}")
            # Return minimal data to prevent further errors
            return {
                'mail_body': f"Error loading message: {str(e)}",
                'mail_from': 'Unknown',
                'subject': 'Error retrieving message',
                'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mail_size': 0,
                'receive_time': datetime.now().timestamp()
            }

    @property
    def service_name(self) -> str:
        return self.SERVICE_NAME
    
    @property
    def domains(self) -> List[str]:
        if self._domains is None:
            return ['mail.gw']  # Default domain
        return self._domains
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        return 600  # 10 minutes


class DropMailAPI:
    """API handler for DropMail.me service."""
    BASE_URL = 'https://dropmail.me/api/graphql/'
    DOMAINS = ['dropmail.me']  # This service generates domains dynamically
    SERVICE_NAME = "DropMail.me"

    def __init__(self):
        pass

    def _rand_str(self, n=10):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    async def _gql_post(self, token, query, variables=None):
        url = self.BASE_URL + token
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        async with aiohttp.ClientSession(headers={'Content-Type': 'application/json'}) as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    raise Exception(f"DropMail API error: {resp.status}")
                data = await resp.json()
                return data.get("data", {})

    async def create_address(self, domain: str = None) -> Dict:
        """Create session and get email address"""
        token = self._rand_str(12)
        query = """
        mutation {
          introduceSession {
            id
            expiresAt
            addresses {
              address
            }
          }
        }
        """
        data = await self._gql_post(token, query)
        sess = data["introduceSession"]
        session_id = sess["id"]
        address = sess["addresses"][0]["address"]
        
        # Return combined token that includes both API token and session ID
        return {'email': address, 'token': f"{token}|{session_id}"}

    async def get_messages(self, token: str) -> List[Dict]:
        """Get messages for the session"""
        api_token, session_id = token.split('|')
        query = """
        query($id: ID!){
          session(id: $id){
            mails{
              id
              fromAddr
              headerSubject
              text
              receivedAt
            }
          }
        }
        """
        data = await self._gql_post(api_token, query, {"id": session_id})
        session = data.get("session")
        if session is None:
            return []
        
        messages = session.get("mails", [])
        
        # Normalize message format
        normalized = []
        for m in messages:
            normalized.append({
                'mail_id': m['id'],
                'subject': m.get('headerSubject', 'No Subject'),
                'mail_from': m.get('fromAddr', 'Unknown'),
                'mail_date': m.get('receivedAt', ''),
                'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
            })
        return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content"""
        try:
            # For DropMail, we need to query for the specific message directly
            api_token, session_id = token.split('|')
            
            # First try the more precise query for a single mail
            try:
                query = """
                query($id: ID!, $mailId: ID!){
                  session(id: $id){
                    mail(id: $mailId){
                      id
                      fromAddr
                      headerSubject
                      text
                      html
                      receivedAt
                      size
                    }
                  }
                }
                """
                data = await self._gql_post(api_token, query, {"id": session_id, "mailId": message_id})
                mail = data.get("session", {}).get("mail", {})
                
                # If we got data, use it
                if mail and (mail.get('text') or mail.get('html')):
                    # Prioritize HTML content if available
                    html_content = mail.get('html', '')
                    text_content = mail.get('text', '')
                    
                    # Get the better content
                    final_content = html_content if html_content else text_content
                    
                    # Calculate size if not provided
                    mail_size = mail.get('size', len(final_content.encode('utf-8')))
                    
                    return {
                        'mail_body': final_content,
                        'mail_from': mail.get('fromAddr', 'Unknown'),
                        'subject': mail.get('headerSubject', 'No Subject'),
                        'mail_date': mail.get('receivedAt', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'mail_size': mail_size,
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    }
            except Exception as e:
                logging.error(f"DropMail single mail query failed: {e}")
                # Continue to fallback method
            
            # If direct mail query failed, fall back to full mail list
            query = """
            query($id: ID!){
              session(id: $id){
                mails{
                  id
                  fromAddr
                  headerSubject
                  text
                  html
                  receivedAt
                }
              }
            }
            """
            data = await self._gql_post(api_token, query, {"id": session_id})
            
            # Find the specific message in the list
            mail = None
            if "session" in data and "mails" in data["session"]:
                for m in data["session"]["mails"]:
                    if m["id"] == message_id:
                        mail = m
                        break
            
            if not mail:
                raise Exception("Message not found in session")
                
            # Prioritize HTML content
            html_content = mail.get('html', '')
            text_content = mail.get('text', '')
            
            # Get the better content
            final_content = html_content if html_content else text_content
            
            # Calculate size based on content
            mail_size = len(final_content.encode('utf-8')) if final_content else 0
            
            return {
                'mail_body': final_content,
                'mail_from': mail.get('fromAddr', 'Unknown'),
                'subject': mail.get('headerSubject', 'No Subject'),
                'mail_date': mail.get('receivedAt', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'mail_size': mail_size,
                'receive_time': datetime.now().timestamp()
            }
        except Exception as e:
            logging.error(f"DropMailAPI fetch_message error: {str(e)}")
            # Return minimal data to prevent further errors
            return {
                'mail_body': f"Error loading message: {str(e)}",
                'mail_from': 'Unknown',
                'subject': 'Error retrieving message',
                'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mail_size': 0,
                'receive_time': datetime.now().timestamp()
            }

    @property
    def service_name(self) -> str:
        return self.SERVICE_NAME
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        return 600  # 10 minutes


class MailTmAPI:
    """API handler for Mail.tm service."""
    BASE_URL = 'https://api.mail.tm'
    SERVICE_NAME = "Mail.tm"

    def __init__(self):
        self._domains = None

    def _generate_random_string(self, length=10):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

    async def _get_domains(self) -> List[str]:
        """Fetch available domains"""
        if self._domains is None:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/domains") as resp:
                    data = await resp.json()
                    member = data.get("hydra:member", [])
                    self._domains = [d["domain"] for d in member]
        return self._domains

    async def create_address(self, domain: str = None) -> Dict:
        """Create new Mail.tm account"""
        if domain is None:
            domains = await self._get_domains()
            if not domains:
                raise Exception("No domains available")
            domain = random.choice(domains)
        
        local = self._generate_random_string(10)
        email = f"{local}@{domain}"
        password = self._generate_random_string(12)
        
        async with aiohttp.ClientSession() as session:
            # Create account
            payload = {"address": email, "password": password}
            async with session.post(f"{self.BASE_URL}/accounts", json=payload) as resp:
                await resp.json()  # Just check for errors
            
            # Get token
            async with session.post(f"{self.BASE_URL}/token", json=payload) as resp:
                data = await resp.json()
                token = data["token"]
        
        return {'email': email, 'token': token}

    async def get_messages(self, token: str) -> List[Dict]:
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.BASE_URL}/messages", headers=headers) as resp:
                data = await resp.json()
                messages = data.get("hydra:member", [])
                
                # Normalize message format
                normalized = []
                for msg in messages:
                    normalized.append({
                        'mail_id': msg['id'],
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                        'mail_date': msg.get('createdAt', ''),
                        'receive_time': datetime.now().timestamp()  # Add timestamp for sorting
                    })
                return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content for Mail.tm"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/messages/{message_id}", headers=headers) as resp:
                    msg = await resp.json()
                    
                    # Prioritize HTML content if available
                    html_content = msg.get('html', '')
                    text_content = msg.get('text', '')
                    
                    # Check if content exists at alternate locations
                    if not html_content and not text_content and 'intro' in msg:
                        text_content = msg.get('intro', '')
                    
                    # Ensure content is a string, not a list
                    if isinstance(html_content, list):
                        html_content = '\n'.join([str(item) for item in html_content])
                    if isinstance(text_content, list):
                        text_content = '\n'.join([str(item) for item in text_content])
                    
                    # Use HTML if available, else text
                    final_content = html_content if html_content else text_content
                    
                    # Calculate size based on content length
                    message_size = len(final_content.encode('utf-8'))
                    
                    # Format date if available
                    created_date = msg.get('createdAt', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    # Normalize message format
                    return {
                        'mail_body': final_content,
                        'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_date': created_date,
                        'mail_size': message_size,
                        'receive_time': datetime.now().timestamp()
                    }
        except Exception as e:
            logging.error(f"MailTmAPI fetch_message error: {str(e)}")
            # Return minimal data to prevent further errors
            return {
                'mail_body': f"Error loading message: {str(e)}",
                'mail_from': 'Unknown',
                'subject': 'Error retrieving message',
                'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mail_size': 0,
                'receive_time': datetime.now().timestamp()
            }

    @property
    def service_name(self) -> str:
        return self.SERVICE_NAME
    
    @property
    def domains(self) -> List[str]:
        if self._domains is None:
            return ['mail.tm']  # Default domain
        return self._domains
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        return 604800  # 7 days


class TempMailLolAPI:
    """API handler for TempMail.lol service."""
    BASE_URL = 'https://api.tempmail.lol'
    DOMAINS = ['tempmail.lol']  # This service generates domains dynamically
    SERVICE_NAME = "TempMail.lol"

    def __init__(self):
        self.message_cache = {}  # Store messages locally

    async def create_address(self, domain: str = None) -> Dict:
        """Generate address using TempMail.lol"""
        # Can use /generate or /generate/rush
        path = "/generate/rush"  # Rush is faster
        url = self.BASE_URL + path
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"TempMail.lol API error: {resp.status}")
                data = await resp.json()
                return {'email': data["address"], 'token': data["token"]}

    async def get_messages(self, token: str) -> List[Dict]:
        """Fetch emails for the token"""
        url = f"{self.BASE_URL}/auth/{token}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"TempMail.lol API error: {resp.status}")
                data = await resp.json()
                messages = data.get("email", [])
                
                # Save messages to cache and normalize format
                if token not in self.message_cache:
                    self.message_cache[token] = []
                
                normalized = []
                existing_ids = {msg['mail_id'] for msg in self.message_cache[token]}
                
                for i, msg in enumerate(messages):
                    msg_id = str(i)
                    if msg_id not in existing_ids:
                        # New message - save to cache
                        received_time = datetime.now().timestamp()
                        normalized_msg = {
                            'mail_id': msg_id,
                            'subject': msg.get('subject', 'No Subject'),
                            'mail_from': msg.get('from', 'Unknown'),
                            'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'mail_body': msg.get('body', '') or msg.get('html', ''),
                            'mail_size': len(msg.get('body', '') or msg.get('html', '')),
                            'cached': False,
                            'receive_time': received_time
                        }
                        self.message_cache[token].append(normalized_msg)
                        normalized.append(normalized_msg)
                
                # Also return cached messages not in current response
                for cached_msg in self.message_cache[token]:
                    if cached_msg['mail_id'] not in [msg['mail_id'] for msg in normalized]:
                        cached_copy = cached_msg.copy()
                        cached_copy['cached'] = True
                        normalized.append(cached_copy)
                
                return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content for TempMail.lol"""
        try:
            # First try to get from cache
            if token in self.message_cache:
                for msg in self.message_cache[token]:
                    if msg['mail_id'] == message_id:
                        # Ensure we have date and size
                        if not msg.get('mail_date'):
                            msg['mail_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        body_content = msg.get('mail_body', '')
                        if not msg.get('mail_size'):
                            msg['mail_size'] = len(body_content.encode('utf-8')) if body_content else 0
                            
                        return {
                            'mail_body': body_content,
                            'mail_from': msg.get('mail_from', 'Unknown'),
                            'subject': msg.get('subject', 'No Subject'),
                            'mail_date': msg.get('mail_date'),
                            'mail_size': msg.get('mail_size'),
                            'receive_time': msg.get('receive_time', datetime.now().timestamp())
                        }
            
            # If not in cache, fetch fresh
            url = f"{self.BASE_URL}/auth/{token}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"TempMail.lol API error: {resp.status}")
                    data = await resp.json()
                    messages = data.get("email", [])
                    
                    try:
                        index = int(message_id)
                        if 0 <= index < len(messages):
                            msg = messages[index]
                            body_content = msg.get('body', '') or msg.get('html', '')
                            
                            # Calculate size based on content length
                            size = len(body_content.encode('utf-8')) if body_content else 0
                            
                            # Use current timestamp if date not provided
                            curr_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            receive_time = datetime.now().timestamp()
                            
                            return {
                                'mail_body': body_content,
                                'mail_from': msg.get('from', 'Unknown'),
                                'subject': msg.get('subject', 'No Subject'),
                                'mail_date': curr_date,
                                'mail_size': size,
                                'receive_time': receive_time
                            }
                    except (ValueError, IndexError):
                        pass
                    
                    # Return a default message if not found
                    return {
                        'mail_body': 'Message not found',
                        'mail_from': 'Unknown',
                        'subject': 'Not found',
                        'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'mail_size': 0,
                        'receive_time': datetime.now().timestamp()
                    }
        except Exception as e:
            logging.error(f"TempMailLolAPI fetch_message error: {str(e)}")
            # Return minimal data to prevent further errors
            return {
                'mail_body': f"Error loading message: {str(e)}",
                'mail_from': 'Unknown',
                'subject': 'Error retrieving message',
                'mail_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'mail_size': 0,
                'receive_time': datetime.now().timestamp()
            }

    @property
    def service_name(self) -> str:
        return self.SERVICE_NAME
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS
    
    @property
    def expiration_seconds(self) -> int:
        """Return expiration time in seconds"""
        return 3600  # 1 hour


# Registry of all available services
SERVICE_REGISTRY = {
    'guerrillamail': GuerrillaMailAPI,
    'mailgw': MailGwAPI,
    'dropmail': DropMailAPI,
    'mailtm': MailTmAPI,
    'tempmaillol': TempMailLolAPI
}
