"""Temporary Email Service APIs for TempMail Pro"""
import random
import string
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Protocol
import requests  # For synchronous APIs
import weakref


# Global session manager to track and clean up sessions
_active_sessions = weakref.WeakSet()


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
    
    async def close(self):
        """Close any open sessions"""
        ...


class GuerrillaMailAPI:
    """API handler for Guerrilla Mail service."""
    BASE_URL = 'https://api.guerrillamail.com/ajax.php'
    DOMAINS = ['grr.la', 'sharklasers.com', 'guerrillamail.net', 'guerrillamail.com']

    def __init__(self):
        self.session = aiohttp.ClientSession(headers=self._default_headers())
        _active_sessions.add(self.session)
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
        
        async with self.session.get(self.BASE_URL, params=params) as resp:
            try:
                data = await resp.json()
                return {'email': data['email_addr'], 'token': data['sid_token']}
            except Exception:
                params = {'f': 'get_email_address'}
                async with self.session.get(self.BASE_URL, params=params) as fallback_resp:
                    data = await fallback_resp.json()
                    return {'email': data['email_addr'], 'token': data['sid_token']}

    async def get_messages(self, token: str) -> List[Dict]:
        params = {'f': 'get_email_list', 'sid_token': token, 'offset': '0'}
        async with self.session.get(self.BASE_URL, params=params) as resp:
            data = await resp.json()
            return data.get('list', [])

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        params = {'f': 'fetch_email', 'sid_token': token, 'email_id': message_id}
        async with self.session.get(self.BASE_URL, params=params) as resp:
            return await resp.json()

    @property
    def service_name(self) -> str:
        return "Guerrilla Mail"
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()


class MailGwAPI:
    """API handler for Mail.gw service."""
    BASE_URL = 'https://api.mail.gw'
    DOMAINS = None  # Will be fetched dynamically

    def __init__(self):
        self.session = aiohttp.ClientSession()
        _active_sessions.add(self.session)
        self._domains = None

    def _randstr(self, n=10):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    async def _get_domains(self) -> List[str]:
        """Fetch available domains"""
        if self._domains is None:
            async with self.session.get(f"{self.BASE_URL}/domains") as resp:
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
        
        # Create account
        async with self.session.post(f"{self.BASE_URL}/accounts", 
                                   json={"address": email, "password": password}) as resp:
            await resp.json()  # Just check for errors
        
        # Get token
        async with self.session.post(f"{self.BASE_URL}/token",
                                   json={"address": email, "password": password}) as resp:
            data = await resp.json()
            token = data["token"]
        
        return {'email': email, 'token': token}

    async def get_messages(self, token: str) -> List[Dict]:
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE_URL}/messages", headers=headers) as resp:
            data = await resp.json()
            messages = data.get("hydra:member", [])
            
            # Normalize message format
            normalized = []
            for msg in messages:
                normalized.append({
                    'mail_id': msg['id'],
                    'subject': msg.get('subject', 'No Subject'),
                    'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                    'mail_date': msg.get('createdAt', '')
                })
            return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE_URL}/messages/{message_id}", headers=headers) as resp:
            msg = await resp.json()
            
            # Normalize message format
            return {
                'mail_body': msg.get('text', '') or msg.get('html', ''),
                'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                'subject': msg.get('subject', 'No Subject'),
                'mail_date': msg.get('createdAt', ''),
                'mail_size': 'N/A'
            }

    @property
    def service_name(self) -> str:
        return "Mail.gw"
    
    @property
    def domains(self) -> List[str]:
        if self._domains is None:
            return ['mail.gw']  # Default domain
        return self._domains

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()


class DropMailAPI:
    """API handler for DropMail.me service."""
    BASE_URL = 'https://dropmail.me/api/graphql/'
    DOMAINS = ['dropmail.me']  # This service generates domains dynamically

    def __init__(self):
        self.session = aiohttp.ClientSession(headers={'Content-Type': 'application/json'})
        _active_sessions.add(self.session)

    def _rand_str(self, n=10):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

    async def _gql_post(self, token, query, variables=None):
        url = self.BASE_URL + token
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        async with self.session.post(url, json=payload, timeout=10) as resp:
            if resp.status != 200:
                raise Exception(f"DropMail API error: {resp.status}")
            data = await resp.json()
            return data["data"]

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
                'mail_date': m.get('receivedAt', '')
            })
        return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        """Fetch full message content"""
        # For DropMail, the message list already contains the text
        # We'll need to query again to get the full content
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
        session = data.get("session", {})
        mails = session.get("mails", [])
        
        # Find the specific message
        for m in mails:
            if m['id'] == message_id:
                return {
                    'mail_body': m.get('text', ''),
                    'mail_from': m.get('fromAddr', 'Unknown'),
                    'subject': m.get('headerSubject', 'No Subject'),
                    'mail_date': m.get('receivedAt', ''),
                    'mail_size': 'N/A'
                }
        
        return {}

    @property
    def service_name(self) -> str:
        return "DropMail.me"
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()


class MailTmAPI:
    """API handler for Mail.tm service."""
    BASE_URL = 'https://api.mail.tm'
    DOMAINS = None  # Will be fetched dynamically

    def __init__(self):
        self.session = aiohttp.ClientSession()
        _active_sessions.add(self.session)
        self._domains = None

    def _generate_random_string(self, length=10):
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choices(chars, k=length))

    async def _get_domains(self) -> List[str]:
        """Fetch available domains"""
        if self._domains is None:
            async with self.session.get(f"{self.BASE_URL}/domains") as resp:
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
        
        # Create account
        payload = {"address": email, "password": password}
        async with self.session.post(f"{self.BASE_URL}/accounts", json=payload) as resp:
            await resp.json()  # Just check for errors
        
        # Get token
        async with self.session.post(f"{self.BASE_URL}/token", json=payload) as resp:
            data = await resp.json()
            token = data["token"]
        
        return {'email': email, 'token': token}

    async def get_messages(self, token: str) -> List[Dict]:
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE_URL}/messages", headers=headers) as resp:
            data = await resp.json()
            messages = data.get("hydra:member", [])
            
            # Normalize message format
            normalized = []
            for msg in messages:
                normalized.append({
                    'mail_id': msg['id'],
                    'subject': msg.get('subject', 'No Subject'),
                    'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                    'mail_date': msg.get('createdAt', '')
                })
            return normalized

    async def fetch_message(self, token: str, message_id: str) -> Dict:
        headers = {"Authorization": f"Bearer {token}"}
        async with self.session.get(f"{self.BASE_URL}/messages/{message_id}", headers=headers) as resp:
            msg = await resp.json()
            
            # Normalize message format
            return {
                'mail_body': msg.get('text', '') or msg.get('html', ''),
                'mail_from': msg.get('from', {}).get('address', 'Unknown'),
                'subject': msg.get('subject', 'No Subject'),
                'mail_date': msg.get('createdAt', ''),
                'mail_size': 'N/A'
            }

    @property
    def service_name(self) -> str:
        return "Mail.tm"
    
    @property
    def domains(self) -> List[str]:
        if self._domains is None:
            return ['mail.tm']  # Default domain
        return self._domains

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()


class TempMailLolAPI:
    """API handler for TempMail.lol service."""
    BASE_URL = 'https://api.tempmail.lol'
    DOMAINS = ['tempmail.lol']  # This service generates domains dynamically

    def __init__(self):
        self.session = aiohttp.ClientSession()
        _active_sessions.add(self.session)
        self.message_cache = {}  # Store messages locally

    async def create_address(self, domain: str = None) -> Dict:
        """Generate address using TempMail.lol"""
        # Can use /generate or /generate/rush
        path = "/generate/rush"  # Rush is faster
        url = self.BASE_URL + path
        
        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"TempMail.lol API error: {resp.status}")
            data = await resp.json()
            return {'email': data["address"], 'token': data["token"]}

    async def get_messages(self, token: str) -> List[Dict]:
        """Fetch emails for the token"""
        url = f"{self.BASE_URL}/auth/{token}"
        async with self.session.get(url) as resp:
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
                    normalized_msg = {
                        'mail_id': msg_id,
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_from': msg.get('from', 'Unknown'),
                        'mail_date': '',  # API doesn't provide date
                        'mail_body': msg.get('body', '') or msg.get('html', ''),
                        'cached': False
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
        """Fetch full message content"""
        # First try to get from cache
        if token in self.message_cache:
            for msg in self.message_cache[token]:
                if msg['mail_id'] == message_id:
                    return {
                        'mail_body': msg['mail_body'],
                        'mail_from': msg['mail_from'],
                        'subject': msg['subject'],
                        'mail_date': '',
                        'mail_size': 'N/A'
                    }
        
        # If not in cache, fetch fresh
        url = f"{self.BASE_URL}/auth/{token}"
        async with self.session.get(url) as resp:
            if resp.status != 200:
                raise Exception(f"TempMail.lol API error: {resp.status}")
            data = await resp.json()
            messages = data.get("email", [])
            
            try:
                index = int(message_id)
                if 0 <= index < len(messages):
                    msg = messages[index]
                    return {
                        'mail_body': msg.get('body', '') or msg.get('html', ''),
                        'mail_from': msg.get('from', 'Unknown'),
                        'subject': msg.get('subject', 'No Subject'),
                        'mail_date': '',
                        'mail_size': 'N/A'
                    }
            except (ValueError, IndexError):
                pass
            
            return {}

    @property
    def service_name(self) -> str:
        return "TempMail.lol"
    
    @property
    def domains(self) -> List[str]:
        return self.DOMAINS

    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()


# Registry of all available services
SERVICE_REGISTRY = {
    'guerrillamail': GuerrillaMailAPI,
    'mailgw': MailGwAPI,
    'dropmail': DropMailAPI,
    'mailtm': MailTmAPI,
    'tempmaillol': TempMailLolAPI
}


async def cleanup_all_sessions():
    """Clean up all active sessions"""
    for session in list(_active_sessions):
        if not session.closed:
            try:
                await session.close()
            except Exception:
                pass