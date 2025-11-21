#!/usr/bin/env python3
"""
Test script to validate Claim Compass setup.
Run this before starting the main app to catch configuration issues.
"""

import os
import sys
from config import Config


def test_imports():
    """Test that all required packages are installed."""
    print("\n🔍 Testing imports...")
    required_packages = [
        ("google.adk", "google-adk"),
        ("google.cloud.discoveryengine_v1beta", "google-cloud-discoveryengine"),
        ("streamlit", "streamlit"),
        ("google.genai", "google-genai"),
    ]
    
    missing = []
    for package, pip_name in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {pip_name}")
        except ImportError:
            print(f"  ✗ {pip_name} - NOT INSTALLED")
            missing.append(pip_name)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
        return False
    
    print("✅ All packages installed")
    return True


def test_config():
    """Test that configuration is valid."""
    print("\n🔍 Testing configuration...")
    try:
        Config.validate()
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False


def test_authentication():
    """Test Google Cloud authentication."""
    print("\n🔍 Testing authentication...")
    
    # Check for credentials
    creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_file:
        print(f"  ✓ Service account key: {creds_file}")
    else:
        print("  ℹ️  Using Application Default Credentials")
    
    try:
        from google.auth import default
        credentials, project = default()
        print(f"  ✓ Authenticated with project: {project}")
        return True
    except Exception as e:
        print(f"  ❌ Authentication failed: {e}")
        print("\n  To fix, run one of:")
        print("    gcloud auth application-default login")
        print("    export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'")
        return False


def test_vision_model():
    """Test that Vision model is accessible."""
    print("\n🔍 Testing Vision model...")
    try:
        from google import genai
        
        client = genai.Client(
            vertexai=True,
            project=Config.PROJECT_ID,
            location=Config.VISION_LOCATION
        )
        
        response = client.models.generate_content(
            model=Config.VISION_MODEL,
            contents="Say 'Hello' if you can read this."
        )
        
        print(f"  ✓ Model {Config.VISION_MODEL} is accessible")
        print(f"  Response: {response.text[:100]}...")
        return True
    except Exception as e:
        print(f"  ❌ Vision model error: {e}")
        print(f"\n  Check that:")
        print(f"    1. Vertex AI API is enabled")
        print(f"    2. Model {Config.VISION_MODEL} exists in {Config.VISION_LOCATION}")
        print(f"    3. Your project has access to this model")
        return False


def test_coordinator_model():
    """Test that Coordinator model is accessible."""
    print("\n🔍 Testing Coordinator model...")
    try:
        from google.adk.models.google_llm import Gemini
        
        model = Gemini(
            model=Config.COORDINATOR_MODEL,
            project_id=Config.PROJECT_ID,
            location=Config.LOCATION
        )
        
        print(f"  ✓ Model {Config.COORDINATOR_MODEL} initialized")
        return True
    except Exception as e:
        print(f"  ❌ Coordinator model error: {e}")
        print(f"\n  Check that:")
        print(f"    1. Model {Config.COORDINATOR_MODEL} exists")
        print(f"    2. Location {Config.LOCATION} is valid")
        return False


def test_discovery_engine():
    """Test Discovery Engine (RAG) access."""
    print("\n🔍 Testing Discovery Engine...")
    try:
        from agents.tools import search_policy_documents
        
        result = search_policy_documents(
            "test query",
            Config.PROJECT_ID,
            Config.LOCATION,
            Config.DATA_STORE_ID
        )
        
        if "Error" in result:
            print(f"  ⚠️  Discovery Engine warning: {result}")
            print(f"\n  This is OK if you haven't uploaded policy documents yet.")
            return True
        else:
            print(f"  ✓ Discovery Engine is accessible")
            return True
    except Exception as e:
        print(f"  ❌ Discovery Engine error: {e}")
        print(f"\n  Check that:")
        print(f"    1. Discovery Engine API is enabled")
        print(f"    2. Data store {Config.DATA_STORE_ID} exists")
        print(f"    3. Documents are uploaded to the data store")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🛡️  Claim Compass Setup Validation")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Authentication", test_authentication),
        ("Vision Model", test_vision_model),
        ("Coordinator Model", test_coordinator_model),
        ("Discovery Engine", test_discovery_engine),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ {name} test failed with exception: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! You're ready to run: streamlit run app.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix the issues above before running the app.")
        return 1


if __name__ == "__main__":
    sys.exit(main())