/**
 * 评论项组件
 *
 * 显示单条评论，包括用户信息、内容、互动按钮
 */

import React, { useState } from 'react';
import { Avatar, Tooltip, Button, Popconfirm, message } from 'antd';
import { UserOutlined, DeleteOutlined, LikeOutlined, LikeFilled } from '@ant-design/icons';
import { formatTimeAgo } from '../communityUtils';
import { useCommentLike } from '../../../hooks/community/useLike';
import type { CommentItemProps } from './types';
import './CommentItem.css';

export const CommentItem: React.FC<CommentItemProps> = ({
  comment,
  currentUserId,
  showReplies = true,
  onReply,
  onDelete,
}) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const { isLiked, likes, isLoading, toggleLike } = useCommentLike({
    commentId: comment.id,
    initialLiked: comment.isLiked || false,
    initialLikes: comment.likes || 0,
  });

  const isOwner = comment.isOwner || comment.author.id === currentUserId;

  const handleDelete = async () => {
    if (!comment.id) return;

    setIsDeleting(true);
    try {
      await onDelete?.(comment.id);
      message.success('删除成功');
    } catch (error) {
      message.error('删除失败');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReply = () => {
    onReply?.(comment);
  };

  return (
    <div className="qm-comment-item">
      <div className="qm-comment-avatar">
        <Avatar
          src={comment.author.avatar}
          icon={!comment.author.avatar ? <UserOutlined /> : undefined}
          size={40}
        />
      </div>

      <div className="qm-comment-content">
        <div className="qm-comment-header">
          <div className="qm-comment-author">
            <span className="qm-comment-author-name">{comment.author.name}</span>
            {comment.author.level && (
              <span className="qm-comment-author-level">Lv{comment.author.level}</span>
            )}
          </div>
          <span className="qm-comment-time">
            {formatTimeAgo(comment.createdAt)}
          </span>
        </div>

        {comment.replyTo && (
          <div className="qm-comment-reply-to">
            回复 <span className="qm-comment-reply-to-name">@{comment.replyTo.name}</span>
          </div>
        )}

        <div className="qm-comment-text">{comment.content}</div>

        <div className="qm-comment-actions">
          <Tooltip title={isLiked ? '取消点赞' : '点赞'}>
            <Button
              type="text"
              size="small"
              className={`qm-comment-like-btn ${isLiked ? 'is-liked' : ''}`}
              onClick={toggleLike}
              loading={isLoading}
            >
              {isLiked ? <LikeFilled /> : <LikeOutlined />}
              <span>{likes}</span>
            </Button>
          </Tooltip>

          <Button
            type="text"
            size="small"
            className="qm-comment-reply-btn"
            onClick={handleReply}
          >
            回复
          </Button>

          {isOwner && (
            <Popconfirm
              title="确定删除这条评论吗？"
              onConfirm={handleDelete}
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={isDeleting}
                className="qm-comment-delete-btn"
              >
                删除
              </Button>
            </Popconfirm>
          )}
        </div>

        {/* 显示回复列表 */}
        {showReplies && comment.replies && comment.replies.length > 0 && (
          <div className="qm-comment-replies">
            {comment.replies.map((reply) => (
              <CommentItem
                key={reply.id}
                comment={reply}
                currentUserId={currentUserId}
                showReplies={false}
                onReply={onReply}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}

        {/* 显示更多回复按钮 */}
        {showReplies && comment.repliesCount > 0 && comment.repliesCount > (comment.replies?.length || 0) && (
          <Button
            type="link"
            size="small"
            className="qm-comment-more-replies"
          >
            查看更多回复 ({comment.repliesCount - (comment.replies?.length || 0)} 条)
          </Button>
        )}
      </div>
    </div>
  );
};
