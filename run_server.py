"""
HarvestLink 2.0 - Server Launcher Script
"""

import uvicorn
from backend.config import HOST, PORT

if __name__ == "__main__":
    print(f"==================================================")
    print(f"HarvestLink 2.0: Multilingual Farmer Marketplace")
    print(f"Official Government Mandi Price Integration")
    print(f"Server launching on http://{HOST}:{PORT}")
    print(f"==================================================")
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=False)
