"""
run_render.py - Arranca solo el bot de Telegram (sin webserver) - v3 FORCE REBUILD
"""
import sys
import os

if __name__ == "__main__":
    print("[RUN_RENDER v3] Iniciando bot de Telegram sin webserver...")
    print(f"[RUN_RENDER v3] Python: {sys.version}")
    print(f"[RUN_RENDER v3] Working dir: {os.getcwd()}")
    print(f"[RUN_RENDER v3] Build timestamp: 2025-11-20T00:00:00Z")
    try:
        import bot_telegram
        bot_telegram.main()
    except Exception as e:
        print(f"[RUN_RENDER v3] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
