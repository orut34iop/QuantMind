/**
 * 点赞功能自定义Hook
 *
 * 实现点赞/取消点赞，支持乐观更新
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import { useState, useCallback } from 'react';
import { message } from 'antd';
import { communityService } from '../../services/communityService';

export interface UseLikeOptions {
  postId: number;
  initialLiked?: boolean;
  initialLikes?: number;
  onSuccess?: (isLiked: boolean, newLikes: number) => void;
  onError?: (error: Error) => void;
}

export interface UseLikeReturn {
  isLiked: boolean;
  likes: number;
  isLoading: boolean;
  toggleLike: () => Promise<void>;
}

/**
 * 点赞Hook
 *
 * @param options 配置选项
 * @returns 点赞状态和操作方法
 *
 * @example
 * ```tsx
 * const { isLiked, likes, toggleLike } = useLike({
 *   postId: 123,
 *   initialLiked: false,
 *   initialLikes: 42
 * });
 *
 * <button onClick={toggleLike}>
 *   {isLiked ? '已赞' : '点赞'} {likes}
 * </button>
 * ```
 */
export function useLike(options: UseLikeOptions): UseLikeReturn {
  const {
    postId,
    initialLiked = false,
    initialLikes = 0,
    onSuccess,
    onError,
  } = options;

  const [isLiked, setIsLiked] = useState(initialLiked);
  const [likes, setLikes] = useState(initialLikes);
  const [isLoading, setIsLoading] = useState(false);

  const toggleLike = useCallback(async () => {
    // 防止重复点击
    if (isLoading) return;

    // 乐观更新：立即更新UI
    const previousLiked = isLiked;
    const previousLikes = likes;
    const newLiked = !isLiked;
    const newLikes = newLiked ? likes + 1 : likes - 1;

    setIsLiked(newLiked);
    setLikes(newLikes);
    setIsLoading(true);

    try {
      // 调用API
      const response = await communityService.toggleLike({
        postId,
        targetType: 'post',
        isLiked: newLiked,
      });

      // API 成功，使用服务器返回的最新数据（communityService 返回已解包的数据）
      if (response) {
        setIsLiked(response.isLiked);
        setLikes(response.likes);
        onSuccess?.(response.isLiked, response.likes);
      } else {
        throw new Error('操作失败');
      }
    } catch (error) {
      // 失败时回滚UI
      console.error('useLike: toggleLike error', error);
      setIsLiked(previousLiked);
      setLikes(previousLikes);

      const errorObj = error instanceof Error ? error : new Error('未知错误');
      message.error(errorObj.message);

      // 错误回调
      onError?.(errorObj);
    } finally {
      setIsLoading(false);
    }
  }, [postId, isLiked, likes, isLoading, onSuccess, onError]);

  return {
    isLiked,
    likes,
    isLoading,
    toggleLike,
  };
}

/**
 * 评论点赞Hook
 *
 * 与帖子点赞类似，但目标类型是comment
 */
export function useCommentLike(options: Omit<UseLikeOptions, 'postId'> & { commentId: number }): UseLikeReturn {
  const {
    commentId,
    initialLiked = false,
    initialLikes = 0,
    onSuccess,
    onError,
  } = options;

  const [isLiked, setIsLiked] = useState(initialLiked);
  const [likes, setLikes] = useState(initialLikes);
  const [isLoading, setIsLoading] = useState(false);

  const toggleLike = useCallback(async () => {
    if (isLoading) return;

    const previousLiked = isLiked;
    const previousLikes = likes;
    const newLiked = !isLiked;
    const newLikes = newLiked ? likes + 1 : likes - 1;

    setIsLiked(newLiked);
    setLikes(newLikes);
    setIsLoading(true);

    try {
      const response = await communityService.toggleLike({
        postId: commentId, // 复用postId字段
        targetType: 'comment',
        isLiked: newLiked,
      });

      if (response) {
        setIsLiked(response.isLiked);
        setLikes(response.likes);
        onSuccess?.(response.isLiked, response.likes);
      } else {
        throw new Error('操作失败');
      }
    } catch (error) {
      console.error('useCommentLike: toggleLike error', error);
      setIsLiked(previousLiked);
      setLikes(previousLikes);

      const errorObj = error instanceof Error ? error : new Error('未知错误');
      message.error(errorObj.message);
      onError?.(errorObj);
    } finally {
      setIsLoading(false);
    }
  }, [commentId, isLiked, likes, isLoading, onSuccess, onError]);

  return {
    isLiked,
    likes,
    isLoading,
    toggleLike,
  };
}
