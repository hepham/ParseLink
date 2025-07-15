# End-to-End Encryption System

## Overview

This system implements **RSA + AES hybrid encryption** for secure client-server communication. The implementation follows industry best practices for end-to-end encryption.

## How It Works

### 1. Key Exchange
- Server generates an RSA key pair (2048-bit) on startup
- Client requests server's public key via `/api/encryption/public-key/`
- Server responds with public key in PEM format

### 2. Encryption Process (Client → Server)
```
1. Client creates AES session key (256-bit)
2. Client encrypts data with AES-CBC + random IV
3. Client encrypts session key with server's RSA public key
4. Client sends both encrypted data and encrypted session key
```

### 3. Decryption Process (Server)
```
1. Server decrypts session key using RSA private key
2. Server decrypts data using AES session key
3. Server processes request normally
4. Server encrypts response using same process
```

## API Endpoints

### Public Key Exchange
```http
GET /api/encryption/public-key/
```

**Response:**
```json
{
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
  "key_size": 2048,
  "algorithm": "RSA"
}
```

### Encryption Test
```http
POST /api/encryption/test/
Content-Type: application/json

{
  "encrypted_data": "base64_encoded_aes_encrypted_data",
  "encrypted_session_key": "base64_encoded_rsa_encrypted_session_key"
}
```

### Encrypted Movie Links
```http
POST /api/encrypted/movie-links/
Content-Type: application/json

{
  "encrypted_data": "base64_encoded_aes_encrypted_data",
  "encrypted_session_key": "base64_encoded_rsa_encrypted_session_key"
}
```

## Implementation Details

### Encryption Components

#### 1. RSA Key Management (`EncryptionManager`)
- **Key Size:** 2048 bits
- **Padding:** OAEP with SHA-256
- **Key Storage:** PEM format in `server_private_key.pem`
- **Key Persistence:** Loads existing keys on startup, generates new if missing

#### 2. AES Encryption (`AESEncryption`)
- **Algorithm:** AES-256-CBC
- **Key Size:** 256 bits (32 bytes)
- **IV:** Random 128-bit IV per encryption
- **Padding:** PKCS7
- **Encoding:** Base64 for transport

#### 3. Hybrid Encryption (`HybridEncryption`)
- **Process:** AES for data, RSA for session key
- **Session Key:** Random 256-bit key per request
- **Format:** JSON with `encrypted_data` and `encrypted_session_key`

### Security Features

✅ **Forward Secrecy:** New session key for each request  
✅ **Secure Randomness:** Uses `secrets` module for key generation  
✅ **Proper Padding:** OAEP for RSA, PKCS7 for AES  
✅ **Strong Algorithms:** RSA-2048 + AES-256-CBC  
✅ **IV Randomization:** Fresh IV for each AES encryption  
✅ **Key Separation:** Different keys for different purposes  

## Client Integration

### 1. Install Dependencies
```bash
pip install cryptography requests
```

### 2. Basic Usage
```python
from client_encryption_example import EncryptionClient

# Initialize client
client = EncryptionClient("http://localhost:8000")

# Make encrypted request
result = client.get_movie_links_encrypted(
    imdb_id="tt4154796",
    tmdb_id="429617"
)

if result['success']:
    print("Movie links:", result['data'])
else:
    print("Error:", result['error'])
```

### 3. Manual Encryption
```python
# Get server public key
response = requests.get("http://localhost:8000/api/encryption/public-key/")
public_key_pem = response.json()['public_key']

# Load public key
from cryptography.hazmat.primitives import serialization
public_key = serialization.load_pem_public_key(public_key_pem.encode())

# Encrypt data
import secrets, json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# 1. Create session key
session_key = secrets.token_bytes(32)

# 2. Encrypt data with AES
data = json.dumps({"imdb_id": "tt1234567"})
# ... (AES encryption code)

# 3. Encrypt session key with RSA
# ... (RSA encryption code)

# 4. Send to server
payload = {
    "encrypted_data": encrypted_data_base64,
    "encrypted_session_key": encrypted_session_key_base64
}
```

## Testing

### Run the Test Client
```bash
python client_encryption_example.py
```

### Test Flow
1. **Key Exchange:** Gets server's public key
2. **Encryption Test:** Tests basic encrypt/decrypt
3. **Movie Links:** Tests real API with encryption
4. **Payload Analysis:** Shows encryption structure

### Expected Output
```
🚀 Starting encrypted client demonstration...
✅ Got server public key (RSA 2048 bits)

==================================================
TEST 1: Basic Encryption Test
==================================================
🔐 Testing encryption functionality...
✅ Encryption test successful!

==================================================
TEST 2: Encrypted Movie Links
==================================================
🎬 Getting movie links (encrypted)...
✅ Movie links retrieved successfully!

==================================================
TEST 3: Encryption Payload Structure
==================================================
- encrypted_data: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
- encrypted_session_key: gAAAAABhZv8sX9QY8HJl2qJ3M4v6QwE...
```

## Security Considerations

### ✅ Secure Practices
- Random session keys for each request
- Proper cryptographic primitives
- Secure padding schemes
- IV randomization
- Key size recommendations

### ⚠️ Important Notes
- Keys stored in plaintext on server filesystem
- No client authentication implemented
- Session keys not persisted
- Response encryption optional

### 🔧 Production Recommendations
1. **Key Management:** Use HSM or secure key storage
2. **Client Auth:** Implement client certificates
3. **Rate Limiting:** Add request throttling
4. **Logging:** Audit encryption operations
5. **Key Rotation:** Implement regular key rotation

## File Structure

```
api/
├── encryption.py          # Main encryption module
├── views.py              # API endpoints with encryption
├── urls.py               # URL routing
└── models.py            # Database models

client_encryption_example.py  # Client demonstration
ENCRYPTION_README.md          # This documentation
requirements.txt             # Updated dependencies
```

## Troubleshooting

### Common Issues

#### 1. Missing Dependencies
```bash
pip install cryptography
```

#### 2. Key Generation Errors
- Check filesystem permissions
- Ensure `server_private_key.pem` is writable
- Delete existing key file to regenerate

#### 3. Encryption Failures
- Verify public key format
- Check payload structure
- Ensure proper base64 encoding

#### 4. Connection Issues
- Verify server is running
- Check firewall settings
- Confirm endpoint URLs

### Debug Mode
Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

### Encryption Overhead
- **RSA Operations:** ~1-2ms per operation
- **AES Operations:** ~0.1ms per KB
- **Key Generation:** ~100ms (one-time)
- **Network Overhead:** ~30% increase in payload size

### Optimization Tips
1. **Batch Requests:** Combine multiple operations
2. **Key Caching:** Cache server public key
3. **Connection Pooling:** Reuse HTTP connections
4. **Compression:** Compress data before encryption

## Examples

### Simple Encryption Test
```python
# Test encryption endpoint
import requests
data = {"message": "Hello World"}
response = requests.post("http://localhost:8000/api/encryption/test/", json=data)
```

### Movie Links with Encryption
```python
# Encrypted movie links request
client = EncryptionClient()
result = client.get_movie_links_encrypted(imdb_id="tt4154796")
```

### Custom Encryption
```python
# Manual encryption process
from api.encryption import hybrid_encryption
encrypted = hybrid_encryption.encrypt_payload({"test": "data"})
decrypted = hybrid_encryption.decrypt_payload(encrypted)
```

## Support

For issues or questions about the encryption system:
1. Check the troubleshooting section
2. Review the client example code
3. Enable debug logging
4. Check server logs for errors

---

**Note:** This encryption system is designed for demonstration purposes. For production use, consider additional security measures and professional security review. 