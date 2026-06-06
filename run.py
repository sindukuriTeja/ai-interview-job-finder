#!/usr/bin/env python3
"""Startup script for AI Interview System."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from models import init_db
from app import app

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('recordings', exist_ok=True)
    init_db()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    mode = 'Development' if debug else 'Production'

    print(f"""
    ╔══════════════════════════════════════════════════════╗
    ║         AI Interview System v2.0                     ║
    ╠══════════════════════════════════════════════════════╣
    ║  URL: http://localhost:{port}                          ║
    ║  Mode: {mode:<12}                                  ║
    ║  Admin: http://localhost:{port}/admin/login             ║
    ║                                                      ║
    ║  Features:                                           ║
    ║  ✓ Resume Upload & AI Parsing (PDF/DOCX)             ║
    ║  ✓ AI Question Generation (Ollama + Rules)           ║
    ║  ✓ Full Video Proctoring with Face Detection         ║
    ║  ✓ Auto Scoring & Real-time Feedback                 ║
    ║  ✓ Anti-Cheat: Paste Detection, Tab Monitoring       ║
    ║  ✓ Admin Dashboard with Analytics                    ║
    ║  ✓ Rate Limiting & Security Headers                  ║
    ║  ✓ Audit Logging & Interview History                 ║
    ║  ✓ Auto-Terminate on Excessive Violations            ║
    ║                                                      ║
    ║  Default Admin: admin / changeme123!                  ║
    ║  (Set ADMIN_USERNAME & ADMIN_PASSWORD env vars)       ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if not debug:
        print("  [!] Running in production mode.")
        print("  [!] Consider using: gunicorn -w 4 -b 0.0.0.0:5000 app:app")
        print()

    app.run(debug=debug, host='0.0.0.0', port=port)
