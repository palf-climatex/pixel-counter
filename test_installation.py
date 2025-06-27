#!/usr/bin/env python3
"""
Test script to verify that all dependencies are properly installed.
"""

import sys

def test_imports():
    """Test that all required packages can be imported."""
    packages = [
        'boto3',
        'rasterio', 
        'geopandas',
        'pandas',
        'numpy',
        'shapely',
        'click'
    ]
    
    failed_imports = []
    
    for package in packages:
        try:
            __import__(package)
            print(f"✓ {package} imported successfully")
        except ImportError as e:
            print(f"✗ Failed to import {package}: {e}")
            failed_imports.append(package)
    
    if failed_imports:
        print(f"\n❌ Failed to import: {', '.join(failed_imports)}")
        print("Please install missing packages with: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ All packages imported successfully!")
        return True

def test_geopandas_data():
    """Test that geopandas can load Natural Earth data."""
    try:
        import geopandas as gpd
        countries = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        print(f"✓ Loaded {len(countries)} countries from Natural Earth data")
        return True
    except Exception as e:
        print(f"✗ Failed to load Natural Earth data: {e}")
        return False

def test_aws_credentials():
    """Test AWS credentials configuration."""
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"✓ AWS credentials configured for account: {identity['Account']}")
        return True
    except Exception as e:
        print(f"✗ AWS credentials not configured or invalid: {e}")
        print("Please run: aws configure")
        return False

def main():
    """Run all tests."""
    print("Testing TIFF Analyzer installation...\n")
    
    tests = [
        ("Package Imports", test_imports),
        ("Geopandas Data", test_geopandas_data),
        ("AWS Credentials", test_aws_credentials)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Testing {test_name}...")
        if test_func():
            passed += 1
        print()
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! You're ready to use the TIFF Analyzer.")
        print("\nTo run the analyzer:")
        print("  python tiff_analyzer_improved.py")
        print("\nFor testing with a limited number of files:")
        print("  python tiff_analyzer_improved.py --limit 5")
    else:
        print("❌ Some tests failed. Please fix the issues above before using the tool.")
        sys.exit(1)

if __name__ == '__main__':
    main() 