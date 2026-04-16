"""
Community Management API Routes (Admin)
--------------------------------------
提供管理员对策略社区内容的审计、置顶、精选及下架功能。
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.routers.community.db import CommentRecord, PostRecord
from backend.services.api.user_app.middleware.auth import require_admin
from backend.shared.database_manager_v2 import get_session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/posts")
async def list_all_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    search: str | None = None,
    current_user: dict = Depends(require_admin),
):
    """管理员获取全量帖子列表（跨租户审计）"""
    logger.info(f"Admin list_all_posts called by user {current_user.get('user_id')}")
    async with get_session(read_only=True) as session:
        stmt = select(PostRecord)

        if category:
            stmt = stmt.where(PostRecord.category == category)
        if search:
            stmt = stmt.where(PostRecord.title.ilike(f"%{search}%"))

        # 计算总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar_one() or 0

        # 排序与分页
        stmt = stmt.order_by(desc(PostRecord.created_at))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await session.execute(stmt)
        posts = result.scalars().all()

        return {
            "success": True,
            "data": {
                "items": [
                    {
                        "id": p.id,
                        "tenant_id": p.tenant_id,
                        "author_id": p.author_id,
                        "title": p.title,
                        "category": p.category,
                        "views": p.views,
                        "likes": p.likes,
                        "comments": p.comments,
                        "pinned": p.pinned,
                        "featured": p.featured,
                        "created_at": p.created_at,
                    }
                    for p in posts
                ],
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
        }


@router.patch("/posts/{post_id}")
async def moderate_post(
    post_id: int,
    pinned: bool | None = None,
    featured: bool | None = None,
    current_user: dict = Depends(require_admin),
):
    """帖子治理：设置置顶或精选"""
    async with get_session(read_only=False) as session:
        stmt = select(PostRecord).where(PostRecord.id == post_id)
        post = (await session.execute(stmt)).scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")

        if pinned is not None:
            post.pinned = pinned
        if featured is not None:
            post.featured = featured

        await session.commit()
        return {"success": True, "message": "治理操作成功"}


@router.delete("/posts/{post_id}")
async def delete_post_admin(
    post_id: int,
    current_user: dict = Depends(require_admin),
):
    """强制下架/删除违规帖子"""
    async with get_session(read_only=False) as session:
        stmt = select(PostRecord).where(PostRecord.id == post_id)
        post = (await session.execute(stmt)).scalar_one_or_none()

        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")

        await session.delete(post)
        await session.commit()
        logger.warning(f"Admin {current_user['user_id']} deleted post {post_id}")
        return {"success": True, "message": "帖子已强制下架"}


@router.get("/stats")
async def get_community_stats(current_user: dict = Depends(require_admin)):
    """社区运行概览统计"""
    async with get_session(read_only=True) as session:
        post_count = (await session.execute(select(func.count(PostRecord.id)))).scalar_one() or 0
        comment_count = (await session.execute(select(func.count(CommentRecord.id)))).scalar_one() or 0
        view_sum = (await session.execute(select(func.sum(PostRecord.views)))).scalar_one() or 0

        return {
            "success": True,
            "data": {
                "total_posts": post_count,
                "total_comments": comment_count,
                "total_views": int(view_sum),
                "status": "active",
            },
        }
