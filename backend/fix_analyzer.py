#!/usr/bin/env python3
with open('analyzers/enhanced_professional_analyzer.py', 'r') as f:
    lines = f.readlines()

# Fix line 365 (index 364)
if 'get_complete_options_chain' in lines[364]:
    lines[364] = '            chain_data = self.thetadata_client.get_complete_options_chain(symbol, expiry_date, current_price)\n'
    lines.insert(365, '            options_chain = chain_data.get("calls", []) + chain_data.get("puts", []) if isinstance(chain_data, dict) else []\n')

# Fix line 590 (now 591 after insert, index 590)
for i, line in enumerate(lines):
    if i > 580 and 'get_complete_options_chain' in line and i != 364:
        lines[i] = '            chain_data = self.thetadata_client.get_complete_options_chain(symbol, expiry_date, current_price)\n'
        lines.insert(i+1, '            options_chain = chain_data.get("calls", []) + chain_data.get("puts", []) if isinstance(chain_data, dict) else []\n')
        break

with open('analyzers/enhanced_professional_analyzer.py', 'w') as f:
    f.writelines(lines)

print("✅ Fixed both occurrences")
