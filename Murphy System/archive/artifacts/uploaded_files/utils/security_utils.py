#!/usr/bin/env python3
"""
Security utilities for credential encryption/decryption using pgcrypto
"""

import psycopg2
from psycopg2 import sql
import json
import hashlib
import os
import base64

class SecurityManager:
    """Manages encryption, decryption, and security operations"""
    
    def __init__(self, db_host='localhost', db_port=5432, db_name='automation_platform', db_user='postgres'):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user
            )
            return True
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def generate_master_key(self, key_name, created_by='system'):
        """
        Generate a new master encryption key
        
        Args:
            key_name: Name for the encryption key
            created_by: User creating the key
            
        Returns:
            Key ID if successful, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Generate a random 256-bit key
            master_key = os.urandom(32)
            
            # Create a hash for verification
            key_hash = hashlib.sha256(master_key).hexdigest()
            
            # Store the encrypted key (in production, this should be stored in a secure HSM)
            # For now, we'll store it as bytea
            cursor.execute(
                """INSERT INTO encryption_keys 
                   (key_name, encrypted_key, key_hash, algorithm, created_by)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING key_id""",
                (key_name, master_key, key_hash, 'aes256', created_by)
            )
            
            key_id = cursor.fetchone()[0]
            self.conn.commit()
            cursor.close()
            
            print(f"✓ Generated master key: {key_name} (ID: {key_id})")
            return key_id
            
        except Exception as e:
            print(f"✗ Error generating master key: {str(e)}")
            self.conn.rollback()
            return None
    
    def encrypt_credentials(self, credentials, key_id):
        """
        Encrypt credentials using pgcrypto
        
        Args:
            credentials: Dictionary of credentials to encrypt
            key_id: ID of the encryption key to use
            
        Returns:
            Encrypted data as bytes, or None on failure
        """
        try:
            cursor = self.conn.cursor()
            
            # Get the encryption key
            cursor.execute(
                "SELECT encrypted_key FROM encryption_keys WHERE key_id = %s AND active = true",
                (key_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                print(f"✗ Encryption key {key_id} not found or inactive")
                return None
            
            key_bytes = result[0]
            
            # Convert credentials to JSON string
            credentials_json = json.dumps(credentials)
            
            # Encrypt using pgcrypto's pgp_sym_encrypt
            cursor.execute(
                "SELECT pgp_sym_encrypt(%s, %s) as encrypted",
                (credentials_json, key_bytes.hex())
            )
            
            encrypted_data = cursor.fetchone()[0]
            cursor.close()
            
            return encrypted_data
            
        except Exception as e:
            print(f"✗ Error encrypting credentials: {str(e)}")
            return None
    
    def decrypt_credentials(self, encrypted_data, key_id):
        """
        Decrypt credentials using pgcrypto
        
        Args:
            encrypted_data: Encrypted data to decrypt
            key_id: ID of the encryption key to use
            
        Returns:
            Decrypted credentials as dictionary, or None on failure
        """
        try:
            cursor = self.conn.cursor()
            
            # Get the encryption key
            cursor.execute(
                "SELECT encrypted_key FROM encryption_keys WHERE key_id = %s AND active = true",
                (key_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                print(f"✗ Decryption key {key_id} not found or inactive")
                return None
            
            key_bytes = result[0]
            
            # Decrypt using pgcrypto's pgp_sym_decrypt
            cursor.execute(
                "SELECT pgp_sym_decrypt(%s, %s) as decrypted",
                (encrypted_data, key_bytes.hex())
            )
            
            decrypted_json = cursor.fetchone()[0]
            cursor.close()
            
            credentials = json.loads(decrypted_json)
            return credentials
            
        except Exception as e:
            print(f"✗ Error decrypting credentials: {str(e)}")
            return None
    
    def store_encrypted_credentials(self, client_id, integration_name, credentials, key_id, 
                                    integration_type='api', auth_type='api_key'):
        """
        Store encrypted credentials for an integration
        
        Args:
            client_id: Client ID
            integration_name: Name of the integration
            credentials: Credentials dictionary to encrypt and store
            key_id: Encryption key ID
            integration_type: Type of integration
            auth_type: Authentication type
            
        Returns:
            Integration ID if successful, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            # Encrypt credentials
            encrypted_data = self.encrypt_credentials(credentials, key_id)
            if not encrypted_data:
                return None
            
            # Check if integration exists
            cursor.execute(
                "SELECT integration_id FROM client_integrations WHERE client_id = %s AND integration_name = %s",
                (client_id, integration_name)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing integration
                cursor.execute(
                    """UPDATE client_integrations 
                       SET encrypted_credentials = %s, encryption_key_id = %s, 
                           is_encrypted = true, credentials = %s, updated_at = NOW()
                       WHERE integration_id = %s""",
                    (encrypted_data, key_id, '{}', existing[0])
                )
                integration_id = existing[0]
            else:
                # Insert new integration
                cursor.execute(
                    """INSERT INTO client_integrations 
                       (client_id, integration_name, integration_type, auth_type, 
                        credentials, encrypted_credentials, encryption_key_id, is_encrypted)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING integration_id""",
                    (client_id, integration_name, integration_type, auth_type,
                     '{}', encrypted_data, key_id, True)
                )
                integration_id = cursor.fetchone()[0]
            
            self.conn.commit()
            cursor.close()
            
            print(f"✓ Stored encrypted credentials for {integration_name}")
            return integration_id
            
        except Exception as e:
            print(f"✗ Error storing encrypted credentials: {str(e)}")
            self.conn.rollback()
            return None
    
    def retrieve_encrypted_credentials(self, integration_id):
        """
        Retrieve and decrypt credentials for an integration
        
        Args:
            integration_id: Integration ID
            
        Returns:
            Decrypted credentials as dictionary, or None on failure
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                """SELECT encrypted_credentials, encryption_key_id, is_encrypted
                   FROM client_integrations 
                   WHERE integration_id = %s""",
                (integration_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                print(f"✗ Integration {integration_id} not found")
                return None
            
            encrypted_data, key_id, is_encrypted = result
            
            if not is_encrypted or not encrypted_data:
                print(f"✓ Integration {integration_id} is not encrypted")
                return {}
            
            # Decrypt credentials
            credentials = self.decrypt_credentials(encrypted_data, key_id)
            cursor.close()
            
            if credentials:
                print(f"✓ Retrieved and decrypted credentials for integration {integration_id}")
            
            return credentials
            
        except Exception as e:
            print(f"✗ Error retrieving encrypted credentials: {str(e)}")
            return None
    
    def log_security_event(self, event_type, event_category, severity='info', 
                          user_id=None, client_id=None, ip_address=None, 
                          user_agent=None, event_details=None, status='success'):
        """
        Log a security event
        
        Args:
            event_type: Type of security event
            event_category: Category of security event
            severity: Severity level (info, warning, critical)
            user_id: User ID
            client_id: Client ID
            ip_address: IP address
            user_agent: User agent string
            event_details: Additional event details as JSON
            status: Event status
            
        Returns:
            Security event ID if successful, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute(
                """INSERT INTO security_events 
                   (event_type, event_category, severity, user_id, client_id, 
                    ip_address, user_agent, event_details, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING security_event_id""",
                (event_type, event_category, severity, user_id, client_id,
                 ip_address, user_agent, json.dumps(event_details or {}), status)
            )
            
            event_id = cursor.fetchone()[0]
            self.conn.commit()
            cursor.close()
            
            return event_id
            
        except Exception as e:
            print(f"✗ Error logging security event: {str(e)}")
            self.conn.rollback()
            return None


def main():
    """Test the security utilities"""
    print("=" * 60)
    print("Security Utilities Test")
    print("=" * 60)
    
    # Initialize security manager
    security = SecurityManager()
    
    if not security.connect():
        print("✗ Failed to connect to database")
        return
    
    print("✓ Connected to database")
    
    # Generate a master key
    key_id = security.generate_master_key("test_master_key", "test_user")
    if not key_id:
        print("✗ Failed to generate master key")
        security.disconnect()
        return
    
    # Test credentials
    test_credentials = {
        "api_key": "sk_test_1234567890abcdef",
        "secret": "secret_key_9876543210",
        "user_id": "user_12345",
        "password": "secure_password"
    }
    
    # Store encrypted credentials
    integration_id = security.store_encrypted_credentials(
        client_id=1,
        integration_name="test_neverbounce",
        credentials=test_credentials,
        key_id=key_id
    )
    
    if not integration_id:
        print("✗ Failed to store encrypted credentials")
        security.disconnect()
        return
    
    # Retrieve and decrypt credentials
    retrieved_credentials = security.retrieve_encrypted_credentials(integration_id)
    
    if retrieved_credentials:
        print("\n✓ Credentials successfully encrypted and decrypted!")
        print(f"Retrieved API Key: {retrieved_credentials['api_key']}")
    else:
        print("\n✗ Failed to retrieve credentials")
    
    # Log a security event
    event_id = security.log_security_event(
        event_type="credentials_access",
        event_category="credential_management",
        severity="info",
        user_id="test_user",
        client_id=1,
        ip_address="192.168.1.1",
        event_details={"integration_id": integration_id}
    )
    
    if event_id:
        print(f"✓ Security event logged (ID: {event_id})")
    
    security.disconnect()
    
    print("\n" + "=" * 60)
    print("Security Utilities Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()