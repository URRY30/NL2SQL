from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.responses import ok
from app.db import get_db_session
from app.schemas.service import ExecuteSqlRequest, GenerateSqlRequest, ServiceQueryRequest
from app.services.agent import NL2SQLAgent


router = APIRouter(prefix="/api", tags=["nl2sql"])
agent = NL2SQLAgent(get_settings())


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db_session)) -> dict:
    return ok(await agent.health(session))


@router.get("/bootstrap")
async def bootstrap(session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        return ok(await agent.bootstrap(session))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/profile")
async def dataset_profile(dataset_id: str, session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        return ok(await agent.dataset_profile(session, dataset_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/query/generate")
async def generate_sql(payload: GenerateSqlRequest, session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        return ok(await agent.generate_sql(session, payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/query/execute")
async def execute_sql(payload: ExecuteSqlRequest, session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        return ok(await agent.execute_sql(session, payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/service/query")
async def service_query(payload: ServiceQueryRequest, session: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        return ok(await agent.service_query(session, payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
