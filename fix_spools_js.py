#!/usr/bin/env python3
"""Fix missing numberDisplay code in spools.js"""

# Read the file
with open('frontend/static/spools.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace: Add numberDisplay logic after trayColor definition
old_code = '''                        const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;

                        let statusBadge = '';'''

new_code = '''                        const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;

                        // NEU: Spulen-Nummern-System
                        const isRFID = s.tray_uuid != null;
                        const spoolNumber = s.spool_number;
                        let numberDisplay = '';

                        if (isRFID) {
                            numberDisplay = '<span class="spool-number-badge rfid-badge" title="RFID-Spule (Bambu)">📡 RFID</span>';
                        } else if (spoolNumber) {
                            numberDisplay = `<span class="spool-number-badge manual-badge" title="Manuelle Spule">#${spoolNumber}</span>`;
                        } else {
                            numberDisplay = '<span class="spool-number-badge" title="Keine Nummer">-</span>';
                        }

                        let statusBadge = '';'''

content = content.replace(old_code, new_code)

# Write updated file
with open('frontend/static/spools.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] Fixed spools.js - numberDisplay logic added!")
