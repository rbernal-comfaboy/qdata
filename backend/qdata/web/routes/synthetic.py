from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from qdata.auth.dependencies import get_current_user
from qdata.db.models import User
from qdata.synthetic.generator import generate
from qdata.synthetic.profiles import PROFILES

router = APIRouter()


class GenerateRequest(BaseModel):
    profile: str = "ventas"
    rows: int = 1000
    null_rate: float = 0.0
    duplicate_rate: float = 0.0
    outlier_rate: float = 0.0
    typo_rate: float = 0.0


@router.post("/generate")
async def generate_synthetic(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
):
    if req.profile not in PROFILES:
        raise HTTPException(status_code=400, detail=f"Perfil no encontrado. Disponibles: {list(PROFILES.keys())}")
    if req.rows > 100000:
        raise HTTPException(status_code=400, detail="Máximo 100,000 filas por solicitud")

    df = generate(
        profile_name=req.profile,
        rows=req.rows,
        null_rate=req.null_rate,
        duplicate_rate=req.duplicate_rate,
        outlier_rate=req.outlier_rate,
        typo_rate=req.typo_rate,
    )

    return {
        "profile": req.profile,
        "rows": len(df),
        "columns": len(df.columns),
        "sample": df.head(10).to_dict("records"),
        "column_types": {str(k): str(v) for k, v in df.dtypes.items()},
    }


@router.get("/profiles")
async def list_profiles():
    return {"profiles": list(PROFILES.keys())}
