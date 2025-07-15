#!/usr/bin/env python3
"""
Client Example for Encrypted Communication
Demonstrates how to use the encryption system to communicate securely with the server

Requirements:
- pip install cryptography requests

Usage:
1. Start the Django server
2. Run this script to test encrypted communication
"""

import requests
import json
import base64
import secrets
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class EncryptionClient:
    """Client-side encryption for communicating with the server"""
    
    def __init__(self, server_url="http://localhost:8000"):
        self.server_url = server_url
        self.server_public_key = None
        self.session = requests.Session()
        
        # Get server's public key
        self._get_server_public_key()
    
    def _get_server_public_key(self):
        """Get server's public key"""
        try:
            response = self.session.get(f"{self.server_url}/api/encryption/public-key/")
            response.raise_for_status()
            
            key_info = response.json()
            public_key_pem = key_info['public_key']
            
            # Load public key
            self.server_public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )
            
            print(f"✅ Got server public key (RSA {key_info['key_size']} bits)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to get server public key: {e}")
            return False
    
    def _generate_session_key(self):
        """Generate AES session key"""
        return secrets.token_bytes(32)  # 256-bit key
    
    def _encrypt_with_aes(self, data, session_key):
        """Encrypt data with AES"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Generate random IV
        iv = secrets.token_bytes(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Pad data
        padding_length = 16 - (len(data) % 16)
        padded_data = data + bytes([padding_length] * padding_length)
        
        # Encrypt
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Return IV + encrypted data
        return base64.b64encode(iv + encrypted_data).decode('utf-8')
    
    def _decrypt_with_aes(self, encrypted_data, session_key):
        """Decrypt data with AES"""
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Extract IV and data
        iv = encrypted_bytes[:16]
        encrypted_data = encrypted_bytes[16:]
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        padding_length = decrypted_padded[-1]
        decrypted_data = decrypted_padded[:-padding_length]
        
        return decrypted_data.decode('utf-8')
    
    def _encrypt_with_rsa(self, data):
        """Encrypt data with server's RSA public key"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted = self.server_public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return base64.b64encode(encrypted).decode('utf-8')
    
    def encrypt_payload(self, data):
        """Encrypt payload using hybrid encryption"""
        if not self.server_public_key:
            raise ValueError("Server public key not available")
        
        # Convert to JSON if needed
        if isinstance(data, dict):
            data = json.dumps(data)
        
        # Generate session key
        session_key = self._generate_session_key()
        
        # Encrypt data with AES
        encrypted_data = self._encrypt_with_aes(data, session_key)
        
        # Encrypt session key with RSA
        encrypted_session_key = self._encrypt_with_rsa(session_key)
        
        return {
            'encrypted_data': encrypted_data,
            'encrypted_session_key': encrypted_session_key
        }
    
    def decrypt_response(self, encrypted_response):
        """Decrypt server response"""
        if not isinstance(encrypted_response, dict):
            return encrypted_response
        
        if 'encrypted_data' not in encrypted_response:
            return encrypted_response
        
        # This is a simplified client decryption
        # In practice, you would need to handle the full hybrid decryption
        # For now, we'll just return the encrypted response structure
        return encrypted_response
    
    def make_encrypted_request(self, endpoint, data):
        """Make encrypted request to server"""
        try:
            # Encrypt the request data
            encrypted_payload = self.encrypt_payload(data)
            
            # Make request
            response = self.session.post(
                f"{self.server_url}/api/{endpoint}",
                json=encrypted_payload,
                headers={'Content-Type': 'application/json'}
            )
            
            # Handle response
            if response.status_code == 200:
                response_data = response.json()
                decrypted_response = self.decrypt_response(response_data)
                return {
                    'success': True,
                    'data': decrypted_response,
                    'status_code': response.status_code
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': None
            }
    
    def test_encryption(self):
        """Test basic encryption functionality"""
        print("\n🔐 Testing encryption functionality...")
        
        # Test encryption test endpoint
        test_data = {
            'message': 'Hello from encrypted client!',
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        result = self.make_encrypted_request('encryption/test/', test_data)
        
        if result['success']:
            print("✅ Encryption test successful!")
            print(f"Response: {json.dumps(result['data'], indent=2)}")
        else:
            print(f"❌ Encryption test failed: {result['error']}")
        
        return result['success']
    
    def get_movie_links_encrypted(self, imdb_id=None, tmdb_id=None):
        """Get movie links using encrypted communication"""
        print(f"\n🎬 Getting movie links (encrypted)...")
        
        request_data = {}
        if imdb_id:
            request_data['imdb_id'] = imdb_id
        if tmdb_id:
            request_data['tmdb'] = tmdb_id
        
        result = self.make_encrypted_request('encrypted/movie-links/', request_data)
        
        if result['success']:
            print("✅ Movie links retrieved successfully!")
            print(f"Response: {json.dumps(result['data'], indent=2)}")
        else:
            print(f"❌ Failed to get movie links: {result['error']}")
        
        return result

def main():
    """Main demonstration function"""
    print("🚀 Starting encrypted client demonstration...")
    
    # Initialize client
    client = EncryptionClient()
    
    if not client.server_public_key:
        print("❌ Cannot proceed without server public key")
        return
    
    # Test 1: Basic encryption test
    print("\n" + "="*50)
    print("TEST 1: Basic Encryption Test")
    print("="*50)
    
    success = client.test_encryption()
    
    if not success:
        print("❌ Basic encryption test failed, skipping movie links test")
        return
    
    # Test 2: Encrypted movie links
    print("\n" + "="*50)
    print("TEST 2: Encrypted Movie Links")
    print("="*50)
    
    # Test with sample movie data
    result = client.get_movie_links_encrypted(
        imdb_id="tt4154796",
        tmdb_id="429617"
    )
    
    if result['success']:
        print("✅ All tests passed!")
    else:
        print("❌ Movie links test failed")
    
    # Test 3: Show encryption payload structure
    print("\n" + "="*50)
    print("TEST 3: Encryption Payload Structure")
    print("="*50)
    
    sample_data = {"imdb_id": "tt1234567", "tmdb": "12345"}
    encrypted_payload = client.encrypt_payload(sample_data)
    
    print("Sample encrypted payload structure:")
    print(f"- encrypted_data: {encrypted_payload['encrypted_data'][:50]}...")
    print(f"- encrypted_session_key: {encrypted_payload['encrypted_session_key'][:50]}...")
    print(f"- encrypted_data length: {len(encrypted_payload['encrypted_data'])} chars")
    print(f"- encrypted_session_key length: {len(encrypted_payload['encrypted_session_key'])} chars")
    
    print("\n🎯 Encryption Features:")
    print("- RSA 2048-bit key for session key encryption")
    print("- AES 256-bit CBC mode for data encryption")
    print("- Random IV for each encryption")
    print("- PKCS7 padding for AES")
    print("- OAEP padding for RSA")
    print("- Base64 encoding for transport")

if __name__ == "__main__":
    main() 