#!/bin/bash

echo "========================================"
echo "Smart AC Voice Controller - Installer"
echo "========================================"
echo ""

echo "[1/3] Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "[2/3] Checking PyAudio installation..."
python3 -c "import pyaudio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "PyAudio not found. Installing..."
    pip3 install pyaudio
fi

echo ""
echo "[3/3] Creating config file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Config file created. Please edit .env and add your API keys."
else
    echo "Config file already exists."
fi

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Gemini API key"
echo "2. Set the Arduino IP address"
echo "3. Run: python3 smart_ac_voice_controller.py"
echo ""

