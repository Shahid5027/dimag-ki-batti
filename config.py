"""
=============================================================
  CAMPUS ECOSYSTEM — AI Configuration
  ─────────────────────────────────────────────────────────
  Change GEMINI_MODEL and GEMINI_API_KEY here ONLY.
  All other files import from this module.
=============================================================
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini Model Version ──────────────────────────────────
# Options (as of May 2026):
#   "gemini-2.0-flash"          ← Fast, stable, recommended ✅
#   "gemini-2.0-flash-lite"     ← Cheaper, lighter tasks
#   "gemini-1.5-flash"          ← Fallback if 2.0 unavailable
#   "gemini-2.5-flash-preview-05-20"  ← Latest preview (may be busy)
GEMINI_MODEL = "gemini-2.5-flash"

# ── API Key ───────────────────────────────────────────────
# Loaded from .env file (GEMINI_API_KEY=your_key_here)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── YouTube Transcript ───────────────────────────────────
# youtube_transcript_api works locally but is BLOCKED on Vercel/cloud.
# On Vercel, users must use the Text or PDF tab instead.
YOUTUBE_ENABLED_LOCALLY = True  # set False to disable even locally
