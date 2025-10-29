#!/bin/bash
###########################################
# STOP TRADING PLATFORM
# Gracefully stops both Python backend and ThetaData Terminal
###########################################

echo "========================================"
echo "🛑 STOPPING TRADING PLATFORM"
echo "========================================"
echo "Time: $(date)"
echo ""

# Stop Python backend
echo "▶️  Stopping Python backend..."
if pgrep -f "app.py" > /dev/null; then
    pkill -f "app.py"
    sleep 2
    # Force kill if still running
    if pgrep -f "app.py" > /dev/null; then
        echo "   ⚠️  Force killing Python backend..."
        pkill -9 -f "app.py"
    fi
    echo "   ✅ Python backend stopped"
else
    echo "   ℹ️  Python backend not running"
fi

# Stop ThetaData Terminal
echo "▶️  Stopping ThetaData Terminal..."
if pgrep -f "ThetaTerminalv3.jar" > /dev/null; then
    pkill -f "ThetaTerminalv3.jar"
    sleep 2
    # Force kill if still running
    if pgrep -f "ThetaTerminalv3.jar" > /dev/null; then
        echo "   ⚠️  Force killing ThetaData Terminal..."
        pkill -9 -f "ThetaTerminalv3.jar"
    fi
    echo "   ✅ ThetaData Terminal stopped"
else
    echo "   ℹ️  ThetaData Terminal not running"
fi

echo ""
echo "========================================"
echo "✅ TRADING PLATFORM STOPPED"
echo "========================================"
