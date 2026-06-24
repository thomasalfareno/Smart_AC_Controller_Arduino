@echo off
echo ========================================
echo Smart AC Voice Controller - Installer
echo ========================================
echo.

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [2/3] Checking PyAudio installation...
python -c "import pyaudio" 2>nul
if %errorlevel% neq 0 (
    echo PyAudio not found. Attempting to install using pipwin...
    pip install pipwin
    pipwin install pyaudio
)

echo.
echo [3/3] Creating config file...
if not exist .env (
    copy .env.example .env
    echo Config file created. Please edit .env and add your API keys.
) else (
    echo Config file already exists.
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env and add your Gemini API key
echo 2. Set the Arduino IP address
echo 3. Run: python smart_ac_voice_controller.py
echo.
pause

