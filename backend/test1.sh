# Quick check
python3 << 'EOF'
from analyzers.enhanced_professional_analyzer import EnhancedProfessionalAnalyzer
analyzer = EnhancedProfessionalAnalyzer(
    polygon_api_key="test",
    tradier_api_key="test"
)
print("Has generate_professional_signal:", hasattr(analyzer, 'generate_professional_signal'))
print("Has analyze_full_gex:", hasattr(analyzer, 'analyze_full_gex'))
EOF