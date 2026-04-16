/**
 * 社区帖子列表 Hook
 *
 * 封装帖子列表的数据获取、缓存、错误处理
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import { useState, useEffect, useCallback } from 'react';
import { communityService, type PostsQueryParams, type PostsResponse } from '../../services/communityService';
import type { CommunityPost, HotTopic, HotUser, PromoCardData } from '../../components/community/types';

/**
 * Hook 状态接口
 */
export interface UseCommunityPostsState {
  posts: CommunityPost[];
  pagination: {
    current: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  hotUsers: HotUser[];
  hotTopics: HotTopic[];
  promo: PromoCardData | null;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook 返回接口
 */
export interface UseCommunityPostsReturn extends UseCommunityPostsState {
  refetch: () => Promise<void>;
  setParams: (params: Partial<PostsQueryParams>) => void;
}

/**
 * 使用社区帖子列表的 Hook
 *
 * @param initialParams 初始查询参数
 * @returns 帖子列表状态和操作方法
 *
 * @example
 * ```tsx
 * const { posts, isLoading, error, refetch } = useCommunityPosts({
 *   sort: '最新',
 *   page: 1,
 *   pageSize: 20
 * });
 * ```
 */
export function useCommunityPosts(
  initialParams: PostsQueryParams = {}
): UseCommunityPostsReturn {
  const [params, setParamsState] = useState<PostsQueryParams>(initialParams);
  const [state, setState] = useState<UseCommunityPostsState>({
    posts: [],
    pagination: {
      current: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
    },
    hotUsers: [],
    hotTopics: [],
    promo: null,
    isLoading: true,
    error: null,
  });

  /**
   * 获取帖子列表
   */
  const fetchPosts = useCallback(async () => {
    (setState as any)((prev: UseCommunityPostsState) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await communityService.getPosts(params);

      if (response && response.posts) {
        (setState as any)((prev: UseCommunityPostsState) => ({
          ...prev,
          posts: response.posts || [],
          pagination: response.pagination || {
            current: params.page || 1,
            pageSize: params.pageSize || 20,
            total: 0,
            totalPages: 0,
          },
          hotUsers: response.hotUsers || [],
          hotTopics: response.hotTopics || [],
          promo: response.promo || null,
          isLoading: false,
          error: null,
        }));
      } else {
        throw new Error('获取帖子列表失败');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('未知错误');
      console.error('useCommunityPosts: fetchPosts error', error);

      (setState as any)((prev: UseCommunityPostsState) => ({
        ...prev,
        isLoading: false,
        error: error,
      }));
    }
  }, [params]);

  /**
   * 设置查询参数
   */
  const setParams = useCallback((newParams: Partial<PostsQueryParams>) => {
    setParamsState({ ...params, ...newParams });
  }, [params]);

  /**
   * 手动刷新
   */
  const refetch = useCallback(async () => {
    await fetchPosts();
  }, [fetchPosts]);

  /**
   * 参数变化时自动获取数据
   */
  useEffect(() => {
    fetchPosts();
  }, [fetchPosts]);

  return {
    ...state,
    refetch,
    setParams,
  };
}

/**
 * 带模拟数据降级的 Hook
 *
 * 如果API请求失败，自动降级到Mock数据
 *
 * @param initialParams 初始查询参数
 * @param mockData Mock数据
 * @param useMock 强制使用Mock数据
 * @returns 帖子列表状态和操作方法
 */
export function useCommunityPostsWithFallback(
  initialParams: PostsQueryParams = {},
  mockData?: PostsResponse,
  useMock: boolean = false
): UseCommunityPostsReturn {
  const [fallbackState, setFallbackState] = useState<UseCommunityPostsState | null>(null);
  const apiResult = useCommunityPosts(initialParams);

  const queryParamsJson = JSON.stringify(initialParams);
  const mockDataJson = JSON.stringify(mockData);

  // 如果强制使用Mock或API失败且有Mock数据，使用Mock数据
  useEffect(() => {
    let newState: UseCommunityPostsState | null = null;

    if (useMock && mockData) {
      console.info('useCommunityPostsWithFallback: Using mock data (forced)');
      newState = {
        posts: mockData.posts || [],
        pagination: mockData.pagination || {
          current: initialParams.page || 1,
          pageSize: initialParams.pageSize || 20,
          total: mockData.posts?.length || 0,
          totalPages: Math.ceil((mockData.posts?.length || 0) / (initialParams.pageSize || 20)),
        },
        hotUsers: mockData.hotUsers || [],
        hotTopics: mockData.hotTopics || [],
        promo: mockData.promo || null,
        isLoading: false,
        error: null,
      };
    } else if (apiResult.error && mockData && apiResult.posts.length === 0) {
      console.warn('useCommunityPostsWithFallback: API failed, falling back to mock data');
      newState = {
        posts: mockData.posts || [],
        pagination: mockData.pagination || {
          current: initialParams.page || 1,
          pageSize: initialParams.pageSize || 20,
          total: mockData.posts?.length || 0,
          totalPages: Math.ceil((mockData.posts?.length || 0) / (initialParams.pageSize || 20)),
        },
        hotUsers: mockData.hotUsers || [],
        hotTopics: mockData.hotTopics || [],
        promo: mockData.promo || null,
        isLoading: false,
        error: null,
      };
    }

    setFallbackState(newState);
  }, [useMock, mockDataJson, apiResult.error, apiResult.posts.length, queryParamsJson]);

  // 如果有fallback状态，使用fallback状态；否则使用API结果
  if (fallbackState) {
    return {
      ...fallbackState,
      refetch: apiResult.refetch,
      setParams: apiResult.setParams,
    };
  }

  return apiResult;
}
