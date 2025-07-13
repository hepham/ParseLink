import requests
import json
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets
import os

class ClientEncryption:
    def __init__(self, server_url="http://localhost:8000"):
        self.server_url = server_url
        self.server_public_key = None
        
    def get_server_public_key(self):
        """Get server's public key"""
        try:
            response = requests.get(f"{self.server_url}/api/encryption/public-key/")
            if response.status_code == 200:
                data = response.json()
                public_key_pem = data['public_key']
                self.server_public_key = serialization.load_pem_public_key(
                    public_key_pem.encode(),
                    backend=default_backend()
                )
                print("✅ Successfully retrieved server public key")
                return True
            else:
                print(f"❌ Failed to get public key: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error getting public key: {e}")
            return False
    
    def generate_aes_key(self):
        """Generate a random AES key"""
        return secrets.token_bytes(32)  # 256-bit key
    
    def encrypt_with_aes(self, data, key):
        """Encrypt data with AES-CBC"""
        # Generate random IV
        iv = secrets.token_bytes(16)
        
        # Pad data to be multiple of 16 bytes
        def pad(data):
            padding_length = 16 - (len(data) % 16)
            return data + bytes([padding_length] * padding_length)
        
        padded_data = pad(data)
        
        # Encrypt
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Return IV + ciphertext
        return iv + ciphertext
    
    def decrypt_with_aes(self, encrypted_data, key):
        """Decrypt data with AES-CBC"""
        # Extract IV and ciphertext
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        # Decrypt
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding
        def unpad(data):
            padding_length = data[-1]
            return data[:-padding_length]
        
        return unpad(padded_data)
    
    def encrypt_with_rsa(self, data):
        """Encrypt data with RSA"""
        if not self.server_public_key:
            raise ValueError("Server public key not available")
        
        return self.server_public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
    
    def send_encrypted_request(self, endpoint, data):
        """Send encrypted request to server"""
        try:
            # Generate AES session key
            session_key = self.generate_aes_key()
            print(f"📦 Generated AES session key: {len(session_key)} bytes")
            
            # Encrypt data with AES
            json_data = json.dumps(data).encode('utf-8')
            encrypted_data = self.encrypt_with_aes(json_data, session_key)
            print(f"🔒 Encrypted data: {len(encrypted_data)} bytes")
            
            # Encrypt session key with RSA
            encrypted_session_key = self.encrypt_with_rsa(session_key)
            print(f"🗝️  Encrypted session key: {len(encrypted_session_key)} bytes")
            
            # Prepare request
            request_data = {
                'encrypted_session_key': base64.b64encode(encrypted_session_key).decode(),
                'encrypted_data': base64.b64encode(encrypted_data).decode()
            }
            
            # Send request
            response = requests.post(f"{self.server_url}{endpoint}", json=request_data)
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Decrypt response
                encrypted_response = base64.b64decode(response_data['encrypted_data'])
                decrypted_response = self.decrypt_with_aes(encrypted_response, session_key)
                
                return json.loads(decrypted_response.decode('utf-8'))
            else:
                print(f"❌ Request failed: {response.status_code}")
                
                # Try to decrypt error response if it's encrypted
                try:
                    response_data = response.json()
                    if 'encrypted_data' in response_data:
                        encrypted_response = base64.b64decode(response_data['encrypted_data'])
                        decrypted_response = self.decrypt_with_aes(encrypted_response, session_key)
                        error_message = json.loads(decrypted_response.decode('utf-8'))
                        print(f"🔓 Decrypted error: {error_message}")
                    else:
                        print(f"Response: {response.text}")
                except:
                    print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error in encrypted request: {e}")
            return None

def test_encrypted_movie_links():
    """Test the encrypted movie links API"""
    print("🚀 Testing Encrypted Movie Links API")
    print("=" * 50)
    
    client = ClientEncryption()
    
    # Step 1: Get server public key
    print("\n1. Getting server public key...")
    if not client.get_server_public_key():
        return False
    
    # Step 2: Test cases
    test_cases = [
        {
            "name": "TMDB ID Test",
            "data": {"tmdb_id": "550"},  # Fight Club
            "description": "Testing with TMDB ID"
        },
        {
            "name": "IMDB ID Test", 
            "data": {"imdb_id": "tt0137523"},  # Fight Club
            "description": "Testing with IMDB ID"
        },
        {
            "name": "Both IDs Test",
            "data": {"tmdb_id": "550", "imdb_id": "tt0137523"},
            "description": "Testing with both TMDB and IMDB IDs"
        },
        {
            "name": "Alternative field name",
            "data": {"tmdb": "550"},
            "description": "Testing with 'tmdb' field name"
        }
    ]
    
    # Step 3: Run tests
    print("\n2. Running encrypted API tests...")
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {test_case['name']} ---")
        print(f"Description: {test_case['description']}")
        print(f"Request data: {test_case['data']}")
        
        result = client.send_encrypted_request("/api/encrypted/movie-links/", test_case['data'])
        
        if result:
            print("✅ Test passed!")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            # Validate response format
            if isinstance(result, list):
                print(f"📊 Received {len(result)} results")
                for idx, item in enumerate(result):
                    print(f"  Result {idx + 1}: ID={item.get('id')}, Has M3U8={bool(item.get('m3u8'))}, Transcript ID={item.get('transcriptid')}")
            else:
                print("⚠️  Unexpected response format")
        else:
            print("❌ Test failed!")
    
    print("\n" + "=" * 50)
    print("🎉 Encrypted Movie Links API Testing Complete!")

if __name__ == "__main__":
    # Make sure the server is running
    try:
        response = requests.get("http://localhost:8000/api/encryption/public-key/")
        if response.status_code == 200:
            test_encrypted_movie_links()
        else:
            print("❌ Server not responding. Make sure Django server is running on localhost:8000")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Django server is running on localhost:8000")
        print("Run: python manage.py runserver") 