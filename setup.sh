#/bin/bash
echo "==================================================="
echo "===    Setting up python_v2ray Development     ==="
echo "==================================================="
echo ""
# --- 1. Check for Python ---
echo "[1/4] Checking for Python installation..."
if  command -v python3 &> /dev/null
then
    echo "   - ERROR: Python 3 is not installed or not in PATH."
    exit 1
fi
echo "   - Python 3 found."
echo ""
# --- 2. Create and Activate Virtual Environment ---
echo "[2/4] Creating Python virtual environment in '.venv'..."
if [  -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
echo ""
# --- 3. Install Python Dependencies ---
echo "[3/4] Installing required Python packages..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "   - Python packages installed successfully."
echo ""
# --- 4. Check for Go ---
echo "[4/4] Checking for Go installation..."
if  command -v go &> /dev/null
then
    echo "   - WARNING: Go is not installed or not in PATH."
else
    echo "   - Go found."
fi
echo ""
echo "==================================================="
echo "===    Setup Complete                          ==="
echo "==================================================="
deactivate
