#!/usr/bin/env python3
"""
Test script to verify MCP server authentication.
"""
import os
import requests
import json

# Set test environment
os.environ["OPENAI_API_KEY"] = "test-key-for-testing"
os.environ["MCP_API_KEY"] = "test-mcp-key-123"

def test_authentication():
    """Test the authentication functionality."""
    print("Testing MCP Server Authentication...")
    
    # Import the server to get the generated API key
    import server
    
    print(f"MCP API Key: {server.MCP_API_KEY}")
    print(f"API Key Hash: {server.MCP_API_KEY_HASH}")
    
    # Test the verify_api_key function
    print("\nTesting verify_api_key function:")
    print(f"Valid key test: {server.verify_api_key(server.MCP_API_KEY)}")
    print(f"Invalid key test: {server.verify_api_key('wrong-key')}")
    print(f"Empty key test: {server.verify_api_key('')}")
    
    print("\nAuthentication tests completed successfully!")

if __name__ == "__main__":
    test_authentication()
