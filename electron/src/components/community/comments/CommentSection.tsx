/**
 * 评论区域容器组件
 *
 * 集成评论输入框和评论列表，管理评论状态
 */

import React, { useState } from 'react';
import { Divider } from 'antd';
import { CommentInput } from './CommentInput';
import { CommentList } from './CommentList';
import { useComments } from '../../../hooks/community/useComments';
import type { Comment, CommentUser } from './types';
import './CommentSection.css';

export interface CommentSectionProps {
  postId: number;
  currentUserId?: string;
  pageSize?: number;
  autoFocus?: boolean;
}

/**
 * 评论区域组件
 *
 * @example
 * ```tsx
 * <CommentSection
 *   postId={123}
 *   currentUserId="user_001"
 *   pageSize={20}
 * />
 * ```
 */
export const CommentSection: React.FC<CommentSectionProps> = ({
  postId,
  currentUserId,
  pageSize = 20,
  autoFocus = false,
}) => {
  const {
    comments,
    loading,
    hasMore,
    total,
    loadMore,
    refresh,
    addComment,
    deleteComment,
  } = useComments({ postId, pageSize, autoLoad: true });

  const [replyingTo, setReplyingTo] = useState<Comment | null>(null);

  /**
   * 提交评论
   */
  const handleSubmit = async (content: string) => {
    await addComment(content, replyingTo?.id);
    setReplyingTo(null);
  };

  /**
   * 回复评论
   */
  const handleReply = (comment: Comment) => {
    setReplyingTo(comment);
  };

  /**
   * 取消回复
   */
  const handleCancelReply = () => {
    setReplyingTo(null);
  };

  /**
   * 删除评论
   */
  const handleDelete = async (commentId: number) => {
    await deleteComment(commentId);
  };

  return (
    <div className="qm-comment-section">
      {/* 评论输入框 */}
      <div className="qm-comment-section-input">
        <CommentInput
          postId={postId}
          parentId={replyingTo?.id}
          replyTo={replyingTo?.author}
          placeholder={replyingTo ? `回复 @${replyingTo.author.name}` : '写下你的评论...'}
          autoFocus={autoFocus || !!replyingTo}
          onSubmit={handleSubmit}
          onCancel={replyingTo ? handleCancelReply : undefined}
        />
      </div>

      <Divider />

      {/* 评论列表 */}
      <CommentList
        postId={postId}
        comments={comments}
        loading={loading}
        hasMore={hasMore}
        currentUserId={currentUserId}
        onLoadMore={loadMore}
        onReply={handleReply}
        onDelete={handleDelete}
      />
    </div>
  );
};
