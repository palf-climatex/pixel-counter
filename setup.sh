#!/bin/bash

# TIFF Analyzer Setup Script

echo "🚀 Setting up TIFF Analyzer..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

echo "✅ pip3 found: $(pip3 --version)"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Test installation
echo "🧪 Testing installation..."
python3 test_installation.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Setup complete! You can now use the TIFF Analyzer:"
    echo ""
    echo "  # Test with a few files:"
    echo "  python3 tiff_analyzer_improved.py --limit 5"
    echo ""
    echo "  # Run full analysis:"
    echo "  python3 tiff_analyzer_improved.py"
    echo ""
    echo "  # See all options:"
    echo "  python3 tiff_analyzer_improved.py --help"
else
    echo "❌ Installation test failed. Please check the errors above."
    exit 1
fi 