import requests
import json
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import secrets

def test_basic_endpoints():
    """Test basic endpoints first"""
    print("🔍 Testing Basic Endpoints")
    print("=" * 40)
    
    # Test health check
    try:
        response = requests.get("http://localhost:8000/api/health/")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Test public key
    try:
        response = requests.get("http://localhost:8000/api/encryption/public-key/")
        print(f"Public key: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Public key length: {len(data.get('public_key', ''))}")
    except Exception as e:
        print(f"Public key failed: {e}")

def test_encryption_test_endpoint():
    """Test the encryption test endpoint"""
    print("\n🔐 Testing Encryption Test Endpoint")
    print("=" * 40)
    
    # Get public key
    response = requests.get("http://localhost:8000/api/encryption/public-key/")
    if response.status_code != 200:
        print("❌ Can't get public key")
        return
    
    public_key_pem = response.json()['public_key']
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode(),
        backend=default_backend()
    )
    
    # Generate AES key and encrypt test data
    session_key = secrets.token_bytes(32)
    test_data = {"message": "Hello World"}
    
    # Encrypt data with AES
    json_data = json.dumps(test_data).encode('utf-8')
    iv = secrets.token_bytes(16)
    
    def pad(data):
        padding_length = 16 - (len(data) % 16)
        return data + bytes([padding_length] * padding_length)
    
    padded_data = pad(json_data)
    cipher = Cipher(algorithms.AES(session_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    encrypted_data = iv + ciphertext
    
    # Encrypt session key with RSA
    encrypted_session_key = public_key.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Send request
    request_data = {
        'encrypted_session_key': base64.b64encode(encrypted_session_key).decode(),
        'encrypted_data': base64.b64encode(encrypted_data).decode()
    }
    
    try:
        response = requests.post("http://localhost:8000/api/encryption/test/", json=request_data)
        print(f"Encryption test: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Encryption test failed: {e}")

def test_movie_links_simple():
    """Test regular movie links endpoint (non-encrypted)"""
    print("\n🎬 Testing Regular Movie Links")
    print("=" * 40)
    
    test_data = {"tmdb_id": "550"}
    try:
        # Test correct URL from URL patterns
        response = requests.post("http://localhost:8000/api/movie-links/with-fallback/", json=test_data)
        print(f"Regular movie links: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response length: {len(str(data))}")
            print(f"Response type: {type(data)}")
            if isinstance(data, list) and len(data) > 0:
                print(f"First item: {data[0]}")
        else:
            print(f"Error response: {response.text[:500]}...")
    except Exception as e:
        print(f"Regular movie links failed: {e}")

def test_encrypted_movie_links_simple():
    """Test encrypted movie links with minimal case"""
    print("\n🔐 Testing Encrypted Movie Links")
    print("=" * 40)
    
    # Get public key
    response = requests.get("http://localhost:8000/api/encryption/public-key/")
    if response.status_code != 200:
        print("❌ Can't get public key")
        return
    
    public_key_pem = response.json()['public_key']
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode(),
        backend=default_backend()
    )
    
    # Generate AES key and encrypt test data
    session_key = secrets.token_bytes(32)
    test_data = {"tmdb_id": "550"}  # Simple test case
    
    # Encrypt data with AES
    json_data = json.dumps(test_data).encode('utf-8')
    iv = secrets.token_bytes(16)
    
    def pad(data):
        padding_length = 16 - (len(data) % 16)
        return data + bytes([padding_length] * padding_length)
    
    padded_data = pad(json_data)
    cipher = Cipher(algorithms.AES(session_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    encrypted_data = iv + ciphertext
    
    # Encrypt session key with RSA
    encrypted_session_key = public_key.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    # Send request
    request_data = {
        'encrypted_session_key': base64.b64encode(encrypted_session_key).decode(),
        'encrypted_data': base64.b64encode(encrypted_data).decode()
    }
    
    try:
        response = requests.post("http://localhost:8000/api/encrypted/movie-links/", json=request_data)
        print(f"Encrypted movie links: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success! Decrypting response...")
            response_data = response.json()
            
            # Decrypt response
            encrypted_response = base64.b64decode(response_data['encrypted_data'])
            
            # Decrypt with AES
            iv = encrypted_response[:16]
            ciphertext = encrypted_response[16:]
            cipher = Cipher(algorithms.AES(session_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remove padding
            def unpad(data):
                padding_length = data[-1]
                return data[:-padding_length]
            
            decrypted_data = unpad(padded_data)
            result = json.loads(decrypted_data.decode('utf-8'))
            print(f"Decrypted result: {result}")
            
        else:
            print(f"❌ Failed with status {response.status_code}")
            # Try to decrypt error if possible
            try:
                response_data = response.json()
                if 'encrypted_data' in response_data:
                    print("Trying to decrypt error message...")
                    encrypted_response = base64.b64decode(response_data['encrypted_data'])
                    
                    # Decrypt with AES
                    iv = encrypted_response[:16]
                    ciphertext = encrypted_response[16:]
                    cipher = Cipher(algorithms.AES(session_key), modes.CBC(iv), backend=default_backend())
                    decryptor = cipher.decryptor()
                    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
                    
                    # Remove padding
                    def unpad(data):
                        padding_length = data[-1]
                        return data[:-padding_length]
                    
                    decrypted_data = unpad(padded_data)
                    error_result = json.loads(decrypted_data.decode('utf-8'))
                    print(f"🔓 Decrypted error: {error_result}")
                else:
                    print(f"Raw error: {response.text[:500]}...")
            except Exception as e:
                print(f"Could not decrypt error: {e}")
                print(f"Raw response: {response.text[:500]}...")
                
    except Exception as e:
        print(f"Encrypted movie links test failed: {e}")

def main():
    print("🚀 Debugging Encryption System")
    print("=" * 50)
    
    test_basic_endpoints()
    test_encryption_test_endpoint()
    test_movie_links_simple()
    test_encrypted_movie_links_simple()
    
    print("\n" + "=" * 50)
    print("🎉 Debug Complete!")

if __name__ == "__main__":
    main() 