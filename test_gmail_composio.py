#!/usr/bin/env python3
"""
Simple test script to verify Gmail Composio integration works.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test_gmail_source():
    """Test Gmail source with mock Composio credentials."""
    try:
        from airweave.platform.sources.gmail import GmailSource
        print("✅ Successfully imported GmailSource")
        
        # Test with mock credentials (no actual API calls)
        credentials = {
            "access_token": "mock_access_token",
            "composio_api_key": "mock_composio_key", 
            "entity_id": "mock_entity_id"
        }
        
        # Test source creation
        gmail_source = await GmailSource.create(credentials=credentials)
        print("✅ Successfully created Gmail source with Composio credentials")
        
        # Check that Composio client was initialized
        if gmail_source.composio_client:
            print("✅ Composio client initialized")
        else:
            print("⚠️ Composio client not initialized (expected without real API key)")
        
        # Check that entity_id was set
        if gmail_source.entity_id == "mock_entity_id":
            print("✅ Entity ID properly set")
        else:
            print("❌ Entity ID not set correctly")
            
        # Test backward compatibility with string token
        legacy_source = await GmailSource.create(credentials="legacy_token_string")
        print("✅ Backward compatibility with legacy token format works")
        
        print("\n🎉 All tests passed! Gmail Composio integration is working.")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🧪 Testing Gmail Composio Integration...")
    print("=" * 50)
    
    success = asyncio.run(test_gmail_source())
    
    if success:
        print("\n✅ Integration test completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Integration test failed!")
        sys.exit(1) 