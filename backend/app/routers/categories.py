from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user_id
from app.repositories import categories as repo
from app.schemas.entities import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(
    prefix="/categories", tags=["categories"], dependencies=[Depends(current_user_id)]
)


@router.get("", response_model=list[CategoryOut])
async def list_categories():
    return [CategoryOut(**c) for c in await repo.list_categories()]


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(body: CategoryCreate):
    return CategoryOut(**await repo.create_category(body.model_dump()))


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(category_id: str, body: CategoryUpdate):
    c = await repo.update_category(category_id, body.model_dump(exclude_none=True))
    if c is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return CategoryOut(**c)


@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: str):
    await repo.delete_category(category_id)
