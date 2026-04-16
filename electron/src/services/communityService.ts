/**
 * 策略社区服务
 *
 * 提供社区相关的API调用，包括帖子列表、详情、互动等
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import { APIClient } from './api-client';
import { SERVICE_URLS } from '../config/services';
import { authService } from '../features/auth/services/authService';
import type {
  CommunityPost,
  CommunitySort,
  HotUser,
  HotTopic,
  PromoCardData,
  PostMedia,
  StrategyMetadata,
} from '../components/community/types';

/**
 * 帖子列表查询参数
 */
export interface PostsQueryParams {
  sort?: CommunitySort;
  search?: string;
  page?: number;
  pageSize?: number;
  category?: string;
  tags?: string[];
}

/**
 * 帖子列表响应
 */
export interface PostsResponse {
  posts: CommunityPost[];
  pagination: {
    current: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  hotUsers?: HotUser[];
  hotTopics?: HotTopic[];
  promo?: PromoCardData;
}

/**
 * 帖子详情响应
 */
export interface PostDetailResponse extends Omit<CommunityPost, 'comments'> {
  content: string;
  authorInfo?: {
    id: string;
    name: string;
    avatar?: string;
    level?: number;
    followers?: number;
  };
  comments?: PostComment[];
  relatedPosts?: CommunityPost[];
}

/**
 * 评论接口
 */
export interface PostComment {
  id: number;
  postId: number;
  content: string;
  author: {
    id: string;
    name: string;
    avatar?: string;
    level?: number;
  };
  createdAt: number;
  updatedAt?: number;
  likes: number;
  isLiked?: boolean;
  parentId?: number;
  replyTo?: {
    id: string;
    name: string;
  };
  replies?: PostComment[];
  repliesCount?: number;
  isDeleted?: boolean;
  isOwner?: boolean;
}

/**
 * 互动操作参数
 */
export interface LikeParams {
  postId: number;
  targetType?: 'post' | 'comment';
  isLiked: boolean;
}

export interface LikeResponse {
  isLiked: boolean;
  likes: number;
}

export interface CollectParams {
  postId: number;
  isCollected: boolean;
}

export interface CollectResponse {
  isCollected: boolean;
  collections: number;
}

export interface CommentParams {
  postId: number;
  content: string;
  parentId?: number;
}

export interface FollowAuthorResponse {
  authorId: string;
  isFollowing: boolean;
  followers: number;
}

export interface GetCommentsParams {
  postId: number;
  page?: number;
  pageSize?: number;
}

export interface CommentsListResponse {
  items: PostComment[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// Create post request 类型
export interface CreatePostRequest {
  title: string;
  content: string;
  category: string;
  tags: string[];
  thumbnail?: string;
  media?: PostMedia;
  mediaFiles?: Array<{
    url: string;
    type: 'image' | 'video' | 'attachment';
    fileName: string;
    fileSize: number;
  }>;
  strategy_metadata?: StrategyMetadata;
}

/**
 * 社区服务类
 */
class CommunityService {
  private client: APIClient;
  private baseURL: string;

  constructor() {
    // 使用统一服务配置
    this.baseURL = SERVICE_URLS.API_GATEWAY;

    this.client = new APIClient({
      baseURL: this.baseURL,
      timeout: 30000,
      retries: 2,
      onUnauthorized: () => {
        console.warn('Community API: Unauthorized, redirecting to login...');
        // 可以在这里触发登录跳转
        // window.location.href = '/login';
      },
    });
  }

  private ensureAuthenticated(action: string): void {
    const token = authService.getAccessToken();
    if (!token) {
      throw new Error(`请先登录后再${action}`);
    }
  }

  /**
   * 获取帖子列表
   *
   * @param params 查询参数
   * @returns 帖子列表和相关数据
   */
  async getPosts(params: PostsQueryParams = {}): Promise<PostsResponse> {
    const {
      sort = '全部',
      search = '',
      page = 1,
      pageSize = 20,
      category,
      tags,
    } = params;

    try {
      const response = await this.client.get<PostsResponse>('/api/v1/community/posts', {
        sort,
        search,
        page,
        pageSize,
        category,
        tags: tags?.join(','),
      });

      return response;
    } catch (error) {
      console.error('CommunityService.getPosts error:', error);
      throw error;
    }
  }

  /**
   * 获取帖子详情
   *
   * @param postId 帖子ID
   * @returns 帖子详细信息
   */
  async getPostDetail(postId: number): Promise<PostDetailResponse> {
    try {
      const response = await this.client.get<PostDetailResponse>(
        `/api/v1/community/posts/${postId}`
      );

      return response;
    } catch (error) {
      console.error('CommunityService.getPostDetail error:', error);
      throw error;
    }
  }

  /**
   * 点赞/取消点赞
   *
   * @param params 点赞参数
   * @returns 操作结果
   */
  async toggleLike(params: LikeParams): Promise<LikeResponse> {
    const { postId, isLiked, targetType = 'post' } = params;
    this.ensureAuthenticated(isLiked ? '点赞' : '取消点赞');

    try {
      const path =
        targetType === 'comment'
          ? `/api/v1/community/comments/${postId}/like`
          : `/api/v1/community/posts/${postId}/like`;
      const response = isLiked
        ? await this.client.post<LikeResponse>(path, { isLiked: true })
        : await this.client.delete<LikeResponse>(path);

      return response;
    } catch (error) {
      console.error('CommunityService.toggleLike error:', error);
      throw error;
    }
  }

  /**
   * 收藏/取消收藏
   *
   * @param params 收藏参数
   * @returns 操作结果
   */
  async toggleCollect(params: CollectParams): Promise<CollectResponse> {
    const { postId, isCollected } = params;
    this.ensureAuthenticated(isCollected ? '收藏' : '取消收藏');

    try {
      const path = `/api/v1/community/posts/${postId}/collect`;
      const response = isCollected
        ? await this.client.post<CollectResponse>(path, { isCollected: true })
        : await this.client.delete<CollectResponse>(path);

      return response;
    } catch (error) {
      console.error('CommunityService.toggleCollect error:', error);
      throw error;
    }
  }

  /**
   * 发表评论
   *
   * @param params 评论参数
   * @returns 新增的评论
   */
  async addComment(params: CommentParams): Promise<PostComment> {
    this.ensureAuthenticated('评论');
    try {
      const response = await this.client.post<PostComment>(
        `/api/v1/community/posts/${params.postId}/comments`,
        {
          content: params.content,
          parentId: params.parentId,
        }
      );

      return response;
    } catch (error) {
      console.error('CommunityService.addComment error:', error);
      throw error;
    }
  }

  /**
   * 获取评论列表
   *
   * @param params 查询参数
   * @returns 评论列表
   */
  async getComments(params: GetCommentsParams): Promise<CommentsListResponse> {
    const { postId, page = 1, pageSize = 20 } = params;

    try {
      const response = await this.client.get<CommentsListResponse>(
        `/api/v1/community/posts/${postId}/comments`,
        { page, pageSize }
      );

      return response;
    } catch (error) {
      console.error('CommunityService.getComments error:', error);
      throw error;
    }
  }

  /**
   * 删除评论
   *
   * @param commentId 评论ID
   * @returns 操作结果
   */
  async deleteComment(commentId: number): Promise<void> {
    this.ensureAuthenticated('删除评论');
    try {
      const response = await this.client.delete<void>(
        `/api/v1/community/comments/${commentId}`
      );

      return response;
    } catch (error) {
      console.error('CommunityService.deleteComment error:', error);
      throw error;
    }
  }

  /**
   * 获取作者关注状态
   */
  async getAuthorFollowStatus(authorId: string): Promise<FollowAuthorResponse> {
    try {
      const response = await this.client.get<FollowAuthorResponse>(
        `/api/v1/community/authors/${encodeURIComponent(authorId)}/follow-status`
      );
      return response;
    } catch (error) {
      console.error('CommunityService.getAuthorFollowStatus error:', error);
      throw error;
    }
  }

  /**
   * 关注作者
   */
  async followAuthor(authorId: string): Promise<FollowAuthorResponse> {
    this.ensureAuthenticated('关注作者');
    try {
      const response = await this.client.post<FollowAuthorResponse>(
        `/api/v1/community/authors/${encodeURIComponent(authorId)}/follow`,
        {}
      );
      return response;
    } catch (error) {
      console.error('CommunityService.followAuthor error:', error);
      throw error;
    }
  }

  /**
   * 取消关注作者
   */
  async unfollowAuthor(authorId: string): Promise<FollowAuthorResponse> {
    this.ensureAuthenticated('取消关注作者');
    try {
      const response = await this.client.delete<FollowAuthorResponse>(
        `/api/v1/community/authors/${encodeURIComponent(authorId)}/follow`
      );
      return response;
    } catch (error) {
      console.error('CommunityService.unfollowAuthor error:', error);
      throw error;
    }
  }

  /**
   * 获取热门用户列表
   *
   * @returns 热门用户列表
   */
  async getHotUsers(): Promise<HotUser[]> {
    try {
      const response = await this.client.get<HotUser[]>('/api/v1/community/hot-users');
      return response;
    } catch (error) {
      console.error('CommunityService.getHotUsers error:', error);
      throw error;
    }
  }

  /**
   * 获取热门话题列表
   *
   * @returns 热门话题列表
   */
  async getHotTopics(): Promise<HotTopic[]> {
    try {
      const response = await this.client.get<HotTopic[]>('/api/v1/community/hot-topics');
      return response;
    } catch (error) {
      console.error('CommunityService.getHotTopics error:', error);
      throw error;
    }
  }


  /**
   * 获取推荐阅读列表
   *
   * @param limit 限制数量
   * @returns 推荐帖子列表
   */
  async getRecommendations(limit: number = 5): Promise<Array<{ id: number; title: string; views: number; comments: number }>> {
    try {
      const response = await this.client.get<Array<{ id: number; title: string; views: number; comments: number }>>(
        '/api/v1/community/posts/recommendations',
        { limit }
      );
      return response;
    } catch (error) {
      console.error('CommunityService.getRecommendations error:', error);
      return []; // 出错时返回空列表而不中断流程
    }
  }

  /**
   * 发布新帖子
   *
   * @param post 帖子数据
   * @returns 新创建的帖子
   */
  async createPost(post: CreatePostRequest): Promise<CommunityPost> {
    this.ensureAuthenticated('发帖');
    try {
      const response = await this.client.post<CommunityPost>(
        '/api/v1/community/posts',
        post as unknown as Record<string, unknown>
      );

      return response;
    } catch (error) {
      console.error('CommunityService.createPost error:', error);
      throw error;
    }
  }

  /**
   * 更新帖子
   *
   * @param postId 帖子ID
   * @param updates 更新的字段
   * @returns 更新后的帖子
   */
  async updatePost(
    postId: number,
    updates: Partial<{
      title: string;
      content: string;
      category: string;
      tags: string[];
      thumbnail?: string;
    }>
  ): Promise<CommunityPost> {
    this.ensureAuthenticated('编辑帖子');
    try {
      const response = await this.client.put<CommunityPost>(
        `/api/v1/community/posts/${postId}`,
        updates
      );

      return response;
    } catch (error) {
      console.error('CommunityService.updatePost error:', error);
      throw error;
    }
  }

  /**
   * 删除帖子
   *
   * @param postId 帖子ID
   * @returns 删除结果
   */
  async deletePost(postId: number): Promise<void> {
    this.ensureAuthenticated('删除帖子');
    try {
      const response = await this.client.delete<void>(
        `/api/v1/community/posts/${postId}`
      );

      return response;
    } catch (error) {
      console.error('CommunityService.deletePost error:', error);
      throw error;
    }
  }

  /**
   * 搜索帖子
   *
   * @param keyword 搜索关键词
   * @param options 搜索选项
   * @returns 搜索结果
   */
  async searchPosts(
    keyword: string,
    options: {
      category?: string;
      tags?: string[];
      dateFrom?: number;
      dateTo?: number;
      page?: number;
      pageSize?: number;
    } = {}
  ): Promise<PostsResponse> {
    try {
      const response = await this.client.get<PostsResponse>('/api/v1/community/search', {
        q: keyword,
        ...options,
        tags: options.tags?.join(','),
      });

      return response;
    } catch (error) {
      console.error('CommunityService.searchPosts error:', error);
      throw error;
    }
  }
}

// 导出单例
export const communityService = new CommunityService();

// 导出类型供外部使用
export type { CommunityService };
