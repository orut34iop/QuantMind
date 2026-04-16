export type CommunitySort = '全部' | '最新' | '最热' | '精华';

/**
 * 帖子媒体类型
 */
export type PostMediaType = 'image' | 'curve' | 'chart' | 'none';

/**
 * 收益曲线数据
 */
export interface CurveData {
  dates: string[];
  returns: number[];
  benchmark?: number[];
  sharpe?: number;
  maxDrawdown?: number;
  annualReturn?: number;
}

/**
 * 帖子媒体内容
 */
export interface PostMedia {
  type: PostMediaType;
  url?: string;           // 图片URL
  curveData?: CurveData;  // 收益曲线数据
  alt?: string;           // 图片描述
}

/**
 * 策略元数据（用于策略分享）
 */
export interface StrategyMetadata {
  strategy_id: string;
  strategy_name: string;
  strategy_type: string;
  performance_summary?: {
    total_return_pct: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
  };
  config?: Record<string, any>;  // 策略配置（可选）
  source_user_id?: string;        // 原作者ID
}

/**
 * 作者详细信息
 */
export interface AuthorInfo {
  id: string;
  name: string;
  avatar?: string;
  bio?: string;
  followers_count?: number;
  following_count?: number;
  posts_count?: number;
  likes_received?: number;
}

export interface CommunityPost {
  id: number;
  title: string;
  excerpt: string;
  content?: string;  // 完整内容（HTML）
  category: string;
  tags: string[];
  views: number;
  comments: number;
  likes: number;
  collections?: number;
  author: string;
  authorAvatar?: string;  // 作者头像
  createdAt: number;
  lastCommentAt: number;
  featured?: boolean;
  pinned?: boolean;
  thumbnail?: string | null;  // 兼容旧字段
  media?: PostMedia;          // 新的媒体字段
  // 互动状态
  isLiked?: boolean;
  isCollected?: boolean;
  // 策略关联（新增）
  strategy_metadata?: StrategyMetadata;
  // 作者详情（新增）
  authorInfo?: AuthorInfo;
}

export interface CommunityPostWithScore extends CommunityPost {
  score: number;
}

export interface HotUser {
  id?: string;
  name: string;
  avatar?: string;
  score: number;
  trend: 'up' | 'down';
}

export interface HotTopic {
  name: string;
  count: number;
}

export interface PromoCardData {
  title: string;
  description: string;
  actionLabel: string;
}
