#!/bin/bash
###########################################
# TRADING PLATFORM STATUS
# Checks if both processes are running
###########################################

echo "========================================"
echo "📊 TRADING PLATFORM STATUS"
echo "========================================"
echo "Time: $(date)"
echo ""

# Check Python backend
echo "Python Backend:"
if pgrep -f "app.py" > /dev/null; then
    PID=$(pgrep -f "app.py")
    echo "  ✅ Running (PID: $PID)"
    echo "  🌐 Dashboard: http://localhost:5001"
else
    echo "  ❌ Not running"
fi

echo ""

# Check ThetaData Terminal
echo "ThetaData Terminal:"
if pgrep -f "ThetaTerminalv3.jar" > /dev/null; then
    PID=$(pgrep -f "ThetaTerminalv3.jar")
    echo "  ✅ Running (PID: $PID)"
    echo "  🌐 API: http://localhost:25503"
else
    echo "  ❌ Not running"
fi

echo ""
echo "========================================"
