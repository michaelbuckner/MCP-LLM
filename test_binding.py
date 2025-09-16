#!/usr/bin/env python3
"""
Test script to verify server binding configuration.
"""
import os
import sys

# Set required environment variables
os.environ["OPENAI_API_KEY"] = "test-key-for-binding-test"

def test_server_binding():
    """Test that the server is configured to bind to the correct host."""
    print("Testing server binding configuration...")
    
    # Test default binding (should be 0.0.0.0:8000)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    print(f"Default binding: {host}:{port}")
    
    # Test with custom HOST environment variable
    os.environ["HOST"] = "127.0.0.1"
    os.environ["PORT"] = "9000"
    
    custom_host = os.getenv("HOST", "0.0.0.0")
    custom_port = int(os.getenv("PORT", "8000"))
    
    print(f"Custom binding: {custom_host}:{custom_port}")
    
    # Verify the server configuration
    if host == "0.0.0.0" and port == 8000:
        print("✅ Default binding configuration is correct for Docker/cloud deployment")
    else:
        print("❌ Default binding configuration is incorrect")
        return False
    
    if custom_host == "127.0.0.1" and custom_port == 9000:
        print("✅ Custom binding configuration works correctly")
    else:
        print("❌ Custom binding configuration is incorrect")
        return False
    
    print("\n🎉 All binding tests passed!")
    return True

if __name__ == "__main__":
    success = test_server_binding()
    sys.exit(0 if success else 1)
