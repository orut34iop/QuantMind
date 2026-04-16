/**
 * 评论管理Hook
 *
 * 管理评论的加载、提交、删除、点赞等操作
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { message } from 'antd';
import { communityService } from '../../services/communityService';
import type { Comment } from '../../components/community/comments/types';
import type { UseCommentsOptions, UseCommentsReturn } from '../../components/community/comments/types';

export function useComments(options: UseCommentsOptions): UseCommentsReturn {
  const { postId, pageSize = 20, autoLoad = true } = options;

  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const loadingRef = useRef(false);
  const commentsRef = useRef<Comment[]>([]);
  const totalRef = useRef(0);

  // 避免闭包拿到旧 state（这里不依赖 setState 的函数式写法，兼容当前项目的类型约束）
  useEffect(() => {
    commentsRef.current = comments;
  }, [comments]);
  useEffect(() => {
    totalRef.current = total;
  }, [total]);

  /**
   * 加载评论列表
   */
  const loadComments = useCallback(async (pageNum: number = 1, append: boolean = false) => {
    if (loadingRef.current) return;

    loadingRef.current = true;
    setLoading(true);
    try {
      const response = await communityService.getComments({
        postId,
        page: pageNum,
        pageSize,
      });

      if (response && response.items) {
        const newComments = response.items || [];

        if (append) {
          setComments([...commentsRef.current, ...newComments]);
        } else {
          setComments(newComments);
        }

        setTotal(response.total || 0);
        setHasMore((response.page || pageNum) < (response.totalPages || 1));
        setPage(pageNum);
      }
    } catch (error) {
      console.error('Failed to load comments:', error);
      message.error('加载评论失败');
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, [postId, pageSize]);

  /**
   * 加载更多评论
   */
  const loadMore = useCallback(async () => {
    if (!hasMore || loading) return;
    await loadComments(page + 1, true);
  }, [hasMore, loading, page, loadComments]);

  /**
   * 刷新评论列表
   */
  const refresh = useCallback(async () => {
    await loadComments(1, false);
  }, [loadComments]);

  /**
   * 添加评论
   */
  const addComment = useCallback(async (
    content: string,
    parentId?: number
  ): Promise<Comment | null> => {
    try {
      const newComment = await communityService.addComment({
        postId,
        content,
        parentId,
      });

      if (newComment) {
        if (parentId) {
          // 回复评论，添加到对应评论的replies中
          setComments(
            commentsRef.current.map((comment) => {
              if (comment.id === parentId) {
                return {
                  ...comment,
                  replies: [...(comment.replies || []), newComment],
                  repliesCount: (comment.repliesCount || 0) + 1,
                };
              }
              return comment;
            })
          );
        } else {
          // 新评论，添加到列表顶部
          setComments([newComment, ...commentsRef.current]);
          setTotal(totalRef.current + 1);
        }

        return newComment;
      }

      throw new Error('评论失败');
    } catch (error) {
      console.error('Failed to add comment:', error);
      throw error;
    }
  }, [postId]);

  /**
   * 删除评论
   */
  const deleteComment = useCallback(async (commentId: number): Promise<boolean> => {
    try {
      await communityService.deleteComment(commentId);

      // 从列表中移除评论（支持删除顶层/回复）
      const prevComments = commentsRef.current;
      const filteredTop = prevComments.filter((comment) => comment.id !== commentId);
      if (filteredTop.length !== prevComments.length) {
        setComments(filteredTop);
      } else {
        setComments(
          prevComments.map((comment) => {
            if (!comment.replies || comment.replies.length === 0) return comment;

            const filteredReplies = comment.replies.filter((reply) => reply.id !== commentId);
            if (filteredReplies.length === comment.replies.length) return comment;

            return {
              ...comment,
              replies: filteredReplies,
              repliesCount: Math.max(0, (comment.repliesCount || 0) - 1),
            };
          })
        );
      }

      // total 主要用于展示/统计，P0 先做 best-effort 调整，后续可改为后端返回的精确统计
      setTotal(Math.max(0, totalRef.current - 1));

      return true;
    } catch (error) {
      console.error('Failed to delete comment:', error);
      throw error;
    }
  }, []);

  // 自动加载
  useEffect(() => {
    if (autoLoad && postId) {
      loadComments(1, false);
    }
  }, [autoLoad, postId]); // 移除 loadComments 避免循环

  return {
    comments,
    loading,
    hasMore,
    total,
    loadMore,
    refresh,
    addComment,
    deleteComment,
  };
}
