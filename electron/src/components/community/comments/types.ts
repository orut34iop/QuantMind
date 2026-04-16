/**
 * 评论系统类型定义
 */

export interface CommentUser {
  id: string;
  name: string;
  avatar?: string;
  level?: number;
}

export interface Comment {
  id: number;
  postId: number;
  content: string;
  author: CommentUser;
  createdAt: number;
  updatedAt?: number;
  likes: number;
  isLiked?: boolean;
  // 回复相关
  parentId?: number;
  replyTo?: CommentUser;
  replies?: Comment[];
  repliesCount?: number;
  // 状态
  isDeleted?: boolean;
  isOwner?: boolean;
}

export interface CommentListProps {
  postId: number;
  comments: Comment[];
  loading?: boolean;
  hasMore?: boolean;
  currentUserId?: string;
  onLoadMore?: () => void;
  onReply?: (comment: Comment) => void;
  onDelete?: (commentId: number) => void;
}

export interface CommentItemProps {
  comment: Comment;
  currentUserId?: string;
  showReplies?: boolean;
  onReply?: (comment: Comment) => void;
  onDelete?: (commentId: number) => void;
}

export interface CommentInputProps {
  postId: number;
  parentId?: number;
  replyTo?: CommentUser;
  placeholder?: string;
  maxLength?: number;
  autoFocus?: boolean;
  onSubmit: (content: string) => Promise<void>;
  onCancel?: () => void;
}

export interface UseCommentsOptions {
  postId: number;
  pageSize?: number;
  autoLoad?: boolean;
}

export interface UseCommentsReturn {
  comments: Comment[];
  loading: boolean;
  hasMore: boolean;
  total: number;
  loadMore: () => Promise<void>;
  refresh: () => Promise<void>;
  addComment: (content: string, parentId?: number) => Promise<Comment | null>;
  deleteComment: (commentId: number) => Promise<boolean>;
}
