from fastapi import APIRouter, HTTPException, Header, Depends
import httpx
from app.core.config import settings
from app.services.kv_storage import StorageService

router = APIRouter()

def verify_api_key(x_api_key: str = Header(None)):
    if not settings.CONTROLLER_API_KEY:
        # If no API key configured, we allow it (for dev)
        return True
    if not x_api_key or x_api_key != settings.CONTROLLER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return True

@router.post("/fetch-auth")
async def fetch_auth(valid: bool = Depends(verify_api_key)):
    """
    Fetches Drive authentication details from the Primary Backend
    and stores them in this controller's Vercel KV.
    """
    try:
        if not settings.CONTROLLER_API_KEY:
            raise HTTPException(status_code=500, detail="CONTROLLER_API_KEY not configured. Cannot authenticate with Primary Backend.")
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.PRIMARY_BACKEND_URL}/api/controllers/auth",
                headers={"X-Controller-API-Key": settings.CONTROLLER_API_KEY},
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch from primary: {response.text}")
                
            data = response.json()
            if data.get("status") != "success":
                raise HTTPException(status_code=500, detail="Unsuccessful response from primary backend")
                
            credentials = data.get("credentials", {})
            for key, value in credentials.items():
                # Save each file content into our KV
                StorageService.save_data(key, value)
                
            return {"status": "success", "message": f"Successfully fetched and saved {len(credentials)} credential files."}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
