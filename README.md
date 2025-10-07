# 🚀 Professional Trading Platform

A modular trading platform with real-time market analysis, leveraged ETF calculations, and more.

## 🎯 Features

### ✅ Active Features
- **Trading Dashboard** - Real-time screener with alerts and signals
- **Leveraged Calculator** - ETF price projections based on underlying movement

### 🔜 Coming Soon
- Backtesting Engine
- Portfolio Tracker
- Advanced Alerts System

---

## 📁 Project Structure

```
trading-platform/
├── backend/
│   ├── app.py                 # Main Flask server
│   ├── config.py              # Configuration
│   ├── api/                   # API endpoints (one file per feature)
│   ├── analyzers/             # Analysis engines
│   ├── utils/                 # Shared utilities
│   └── data/                  # Data storage (watchlist, pairs)
├── frontend/
│   ├── dashboard.html         # Main landing page
│   ├── leveraged-calculator.html  # Leveraged ETF tool
│   └── shared/                # Shared CSS/JS
└── .env                       # Your configuration (create this)
```

---

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.8+
- Polygon.io API key (get free at https://polygon.io)

### Step 1: Clone/Create Project
```bash
# If starting fresh, create the folder structure
mkdir trading-platform
cd trading-platform
```

### Step 2: Install Dependencies
```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r backend/requirements.txt
```

### Step 3: Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Polygon API key
nano .env  # or use any text editor
```

Your `.env` should look like:
```
POLYGON_API_KEY=your_actual_api_key_here
PORT=5001
DEBUG=True
```

### Step 4: Start the Server
```bash
# From the project root directory
cd backend
python app.py
```

You should see:
```
Starting Trading Platform on port 5001
Dashboard URL: http://localhost:5001
```

### Step 5: Open Dashboard
Open your browser and navigate to:
```
http://localhost:5001
```

---

## 🎮 Using the Platform

### Main Dashboard
- **Landing page** showing your watchlist with real-time analysis
- **Add symbols** to watchlist via `backend/data/watchlist.txt`
- **Alerts** for trading signals (coming soon with enhanced analyzer)

### Leveraged Calculator
1. Click **"📊 LEVERAGED CALC"** button in dashboard header
2. Opens in new tab
3. Use sliders to project leveraged ETF prices
4. Add custom pairs via **⚙️ SETTINGS**

---

## 📝 Adding Symbols to Watchlist

Edit `backend/data/watchlist.txt`:
```txt
# Trading Watchlist
SPY
QQQ
NVDA
TSLA
AAPL
PLTR

# Add your symbols below:
AMD
COIN
```

Symbols will appear in dashboard after refresh.

---

## 🔧 API Endpoints

### Dashboard Endpoints
```
GET  /api/dashboard/watchlist           # Get all watchlist symbols
POST /api/dashboard/watchlist/add       # Add symbol
POST /api/dashboard/watchlist/remove    # Remove symbol
GET  /api/dashboard/analyze/:symbol     # Analyze single symbol
```

### Leveraged Calculator Endpoints
```
GET  /api/leveraged/pairs               # Get configured pairs
POST /api/leveraged/pairs               # Add new pair
GET  /api/leveraged/calculate           # Calculate projected price
GET  /api/leveraged/price/:symbol       # Get current price
POST /api/leveraged/batch-prices        # Get multiple prices
```

---

## 🎨 Customization

### Adding New Features
1. Create new analyzer in `backend/analyzers/`
2. Create new routes in `backend/api/`
3. Register blueprint in `backend/app.py`
4. Create frontend HTML in `frontend/`
5. Add button to dashboard

Example:
```python
# backend/api/my_feature_routes.py
from flask import Blueprint
my_feature_bp = Blueprint('my_feature', __name__)

@my_feature_bp.route('/endpoint')
def my_endpoint():
    return {'success': True}

# backend/app.py
from api.my_feature_routes import my_feature_bp
app.register_blueprint(my_feature_bp, url_prefix='/api/my-feature')
```

---

## 🐛 Troubleshooting

### "POLYGON_API_KEY not set"
- Make sure `.env` file exists in project root
- Check API key is correct in `.env`
- Restart the server after changing `.env`

### "Module not found" errors
```bash
# Make sure you're in the backend directory
cd backend
python app.py
```

### Port already in use
```bash
# Change port in .env
PORT=5002

# Or kill process on port 5001
# On Mac/Linux: lsof -ti:5001 | xargs kill
# On Windows: netstat -ano | findstr :5001
```

### No data loading
- Check Polygon API key is valid
- Verify watchlist.txt has symbols
- Check browser console for errors (F12)

---

## 📚 Next Steps

### Add Enhanced Analyzer (For Real Signals)
The dashboard currently shows placeholder data. To enable real analysis:

1. Copy your `enhanced_professional_analyzer.py` to `backend/analyzers/`
2. Copy your `opening_range_analyzer.py` to `backend/analyzers/`
3. Update `backend/api/dashboard_routes.py` to use them
4. Restart server

### Customize Styling
All pages use `frontend/shared/terminal-theme.css`. Edit this file to change colors, fonts, etc. across the entire platform.

---

## 🚀 Future Roadmap

- [ ] Backtesting engine
- [ ] Portfolio tracking
- [ ] Advanced alert system
- [ ] User authentication
- [ ] Database integration
- [ ] Mobile app
- [ ] Commercial deployment

---

## 📄 License

Private project - Not for redistribution

---

## 🤝 Support

For issues or questions, check:
- API documentation: https://polygon.io/docs
- Flask documentation: https://flask.palletsprojects.com/

---

**Happy Trading! 📈💰**
