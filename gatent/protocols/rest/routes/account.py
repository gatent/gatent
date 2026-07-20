from fastapi import APIRouter, Depends

from gatent.protocols.rest.dependencies import caller_identity

router = APIRouter(tags=["account"])


@router.get("/me")
async def me(identity: dict = Depends(caller_identity)) -> dict:
    return identity
