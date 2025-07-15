#!/usr/bin/env python3
"""
End-to-End Encryption Module
Implements RSA + AES hybrid encryption for secure client-server communication

Usage:
1. Server generates RSA key pair
2. Client gets server's public key
3. Client creates AES session key, encrypts data with AES, encrypts session key with RSA
4. Server decrypts session key with RSA private key, then decrypts data with AES
"""

import os
import json
import base64
import logging
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
import secrets
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Manages RSA key pair and provides encryption/decryption services"""
    
    def __init__(self, key_size=2048):
        self.key_size = key_size
        self.private_key = None
        self.public_key = None
        self.key_file = 'server_private_key.pem'
        
        # Load or generate RSA key pair
        self._load_or_generate_keys()
    
    def _load_or_generate_keys(self):
        """Load existing keys or generate new ones"""
        try:
            if os.path.exists(self.key_file):
                # Load existing private key
                with open(self.key_file, 'rb') as f:
                    self.private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend()
                    )
                self.public_key = self.private_key.public_key()
                logger.info("Loaded existing RSA key pair")
            else:
                # Generate new key pair
                self._generate_key_pair()
                logger.info("Generated new RSA key pair")
        except Exception as e:
            logger.error(f"Error loading keys: {e}")
            # Fallback to generating new keys
            self._generate_key_pair()
    
    def _generate_key_pair(self):
        """Generate new RSA key pair"""
        # Generate private key
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.key_size,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        
        # Save private key to file
        pem_private = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(self.key_file, 'wb') as f:
            f.write(pem_private)
        
        logger.info(f"Generated and saved new RSA key pair to {self.key_file}")
    
    def get_public_key_pem(self):
        """Get public key in PEM format for client"""
        pem_public = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem_public.decode('utf-8')
    
    def get_public_key_dict(self):
        """Get public key as dictionary for JSON response"""
        return {
            'public_key': self.get_public_key_pem(),
            'key_size': self.key_size,
            'algorithm': 'RSA'
        }
    
    def encrypt_with_public_key(self, data):
        """Encrypt data with public key (for testing)"""
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        encrypted = self.public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_with_private_key(self, encrypted_data):
        """Decrypt data with private key"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            decrypted = self.private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"RSA decryption failed: {e}")
            raise ValueError("Failed to decrypt RSA data")

class AESEncryption:
    """Handles AES encryption/decryption"""
    
    @staticmethod
    def generate_session_key():
        """Generate a random AES session key"""
        return secrets.token_bytes(32)  # 256-bit key
    
    @staticmethod
    def encrypt_data(data, session_key):
        """Encrypt data with AES using session key"""
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Generate random IV
            iv = secrets.token_bytes(16)  # 128-bit IV
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(session_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Pad data to be multiple of 16 bytes
            padded_data = AESEncryption._pad_data(data)
            
            # Encrypt
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Combine IV + encrypted data
            result = iv + encrypted_data
            
            return base64.b64encode(result).decode('utf-8')
            
        except Exception as e:
            logger.error(f"AES encryption failed: {e}")
            raise ValueError("Failed to encrypt data with AES")
    
    @staticmethod
    def decrypt_data(encrypted_data, session_key):
        """Decrypt data with AES using session key"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # Extract IV and encrypted data
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
            decrypted_data = AESEncryption._unpad_data(decrypted_padded)
            
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"AES decryption failed: {e}")
            raise ValueError("Failed to decrypt data with AES")
    
    @staticmethod
    def _pad_data(data):
        """Add PKCS7 padding to data"""
        padding_length = 16 - (len(data) % 16)
        padding = bytes([padding_length] * padding_length)
        return data + padding
    
    @staticmethod
    def _unpad_data(padded_data):
        """Remove PKCS7 padding from data"""
        padding_length = padded_data[-1]
        return padded_data[:-padding_length]

class HybridEncryption:
    """Implements RSA + AES hybrid encryption"""
    
    def __init__(self, encryption_manager):
        self.encryption_manager = encryption_manager
    
    def encrypt_payload(self, data, public_key_pem=None):
        """
        Encrypt payload using hybrid encryption (for testing from server side)
        Returns: {
            'encrypted_data': '...',  # AES encrypted
            'encrypted_session_key': '...'  # RSA encrypted
        }
        """
        try:
            # Generate session key
            session_key = AESEncryption.generate_session_key()
            
            # Encrypt data with AES
            encrypted_data = AESEncryption.encrypt_data(data, session_key)
            
            # Encrypt session key with RSA
            if public_key_pem:
                # Use provided public key
                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
                encrypted_session_key = public_key.encrypt(
                    session_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
            else:
                # Use server's public key
                encrypted_session_key = self.encryption_manager.public_key.encrypt(
                    session_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
            
            return {
                'encrypted_data': encrypted_data,
                'encrypted_session_key': base64.b64encode(encrypted_session_key).decode('utf-8')
            }
            
        except Exception as e:
            logger.error(f"Hybrid encryption failed: {e}")
            raise ValueError("Failed to encrypt payload")
    
    def decrypt_payload(self, encrypted_payload):
        """
        Decrypt payload using hybrid encryption
        Args:
            encrypted_payload: {
                'encrypted_data': '...',  # AES encrypted
                'encrypted_session_key': '...'  # RSA encrypted
            }
        Returns: original data string
        """
        try:
            # Extract components
            encrypted_data = encrypted_payload['encrypted_data']
            encrypted_session_key = encrypted_payload['encrypted_session_key']
            
            # Decrypt session key with RSA
            session_key_bytes = base64.b64decode(encrypted_session_key)
            session_key = self.encryption_manager.private_key.decrypt(
                session_key_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # Decrypt data with AES
            decrypted_data = AESEncryption.decrypt_data(encrypted_data, session_key)
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Hybrid decryption failed: {e}")
            raise ValueError("Failed to decrypt payload")

# Global encryption manager instance
encryption_manager = EncryptionManager()
hybrid_encryption = HybridEncryption(encryption_manager)

def get_public_key():
    """Get server's public key for clients"""
    return encryption_manager.get_public_key_dict()

def encrypt_response(data):
    """Encrypt response data before sending to client"""
    if isinstance(data, (dict, list)):
        data = json.dumps(data)
    return hybrid_encryption.encrypt_payload(data)

def encrypt_response_with_session_key(data, session_key):
    """Encrypt response data using provided session key"""
    if isinstance(data, (dict, list)):
        data = json.dumps(data)
    
    # Encrypt with AES using the provided session key
    encrypted_data = AESEncryption.encrypt_data(data, session_key)
    
    return {
        'encrypted_data': encrypted_data,
        'encrypted_session_key': ''  # No need to send session key back
    }

def decrypt_request(encrypted_payload):
    """Decrypt incoming request data"""
    try:
        decrypted_json = hybrid_encryption.decrypt_payload(encrypted_payload)
        return json.loads(decrypted_json)
    except json.JSONDecodeError:
        return decrypted_json  # Return as string if not JSON

def decrypt_request_and_get_session_key(encrypted_payload):
    """Decrypt request and return both data and session key"""
    try:
        # Extract components (same as decrypt_payload)
        encrypted_data = encrypted_payload['encrypted_data']
        encrypted_session_key = encrypted_payload['encrypted_session_key']
        
        # Decrypt session key with RSA (same as decrypt_payload)
        session_key_bytes = base64.b64decode(encrypted_session_key)
        session_key = encryption_manager.private_key.decrypt(
            session_key_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data with AES (same as decrypt_payload)
        decrypted_data = AESEncryption.decrypt_data(encrypted_data, session_key)
        
        # Parse JSON if possible
        try:
            parsed_data = json.loads(decrypted_data)
        except json.JSONDecodeError:
            parsed_data = decrypted_data
        
        return parsed_data, session_key
        
    except Exception as e:
        logger.error(f"Failed to decrypt request and extract session key: {e}")
        raise ValueError("Failed to decrypt request")

def is_encrypted_request(request_data):
    """Check if request contains encrypted payload"""
    return (
        isinstance(request_data, dict) and 
        'encrypted_data' in request_data and 
        'encrypted_session_key' in request_data
    )

# Decorator for encrypting responses
def encrypt_response_decorator(func):
    """Decorator to automatically encrypt API responses"""
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        if hasattr(response, 'data'):
            encrypted_payload = encrypt_response(response.data)
            response.data = encrypted_payload
        return response
    return wrapper

# Decorator for decrypting requests
def decrypt_request_decorator(func):
    """Decorator to automatically decrypt API requests"""
    def wrapper(self, request, *args, **kwargs):
        if hasattr(request, 'data') and is_encrypted_request(request.data):
            try:
                decrypted_data = decrypt_request(request.data)
                request.data = decrypted_data
            except Exception as e:
                logger.error(f"Failed to decrypt request: {e}")
                return JsonResponse({'error': 'Invalid encrypted request'}, status=400)
        return func(self, request, *args, **kwargs)
    return wrapper 