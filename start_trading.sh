#!/bin/bash
###########################################
# START TRADING PLATFORM
# Starts both Python backend and ThetaData Terminal
###########################################

# Set paths
BACKEND_DIR="~/Desktop/trading-platform/trading-platform/backend"
THETA_DIR="~/Desktop/trading-platform/trading-platform"
LOG_DIR="~Desktop/trading-platform/trading-platform/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Timestamp for logs
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "========================================"
echo "🚀 STARTING TRADING PLATFORM"
echo "========================================"
echo "Time: $(date)"
echo ""

# Check if already running
if pgrep -f "app.py" > /dev/null; then
    echo "⚠️  Python backend already running"
else
    echo "▶️  Starting Python backend..."
    cd "$BACKEND_DIR"
    nohup python3 app.py > "$LOG_DIR/app_$TIMESTAMP.log" 2>&1 &
    echo "   PID: $!"
    sleep 2
fi

if pgrep -f "ThetaTerminalv3.jar" > /dev/null; then
    echo "⚠️  ThetaData Terminal already running"
else
    echo "▶️  Starting ThetaData Terminal..."
    cd "$THETA_DIR"
    nohup java -jar ThetaTerminalv3.jar > "$LOG_DIR/theta_$TIMESTAMP.log" 2>&1 &
    echo "   PID: $!"
    sleep 3
fi

echo ""
echo "========================================"
echo "✅ TRADING PLATFORM STARTED"
echo "========================================"
echo "Backend: http://localhost:5001"
echo "ThetaData: http://localhost:25503"
echo ""
echo "Logs:"
echo "  - Backend: $LOG_DIR/app_$TIMESTAMP.log"
echo "  - ThetaData: $LOG_DIR/theta_$TIMESTAMP.log"
echo ""
echo "To stop: ./stop_trading.sh"
echo "========================================"
