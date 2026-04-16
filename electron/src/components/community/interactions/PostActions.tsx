/**
 * 帖子互动按钮组
 *
 * 集成点赞、评论、收藏、分享等所有互动功能
 */

import React from 'react';
import { MessageOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { LikeButton } from './LikeButton';
import { CollectButton } from './CollectButton';
import { ShareButton } from './ShareButton';
import { AddStrategyButton } from './AddStrategyButton';
import type { CommunityPost } from '../types';
import './InteractionButtons.css';

export interface PostActionsProps {
  post?: CommunityPost;  // 完整帖子数据（用于策略添加）
  postId: number;
  postTitle: string;
  likes: number;
  comments: number;
  collections?: number;
  isLiked?: boolean;
  isCollected?: boolean;
  size?: 'small' | 'medium' | 'large';
  showCommentButton?: boolean;
  showCollectButton?: boolean;
  showShareButton?: boolean;
  showAddStrategyButton?: boolean;  // 是否显示"添加到我的策略"按钮
  onCommentClick?: () => void;
  onLikeChange?: (isLiked: boolean, likes: number) => void;
  onCollectChange?: (isCollected: boolean, collections: number) => void;
  onAddStrategySuccess?: () => void;  // 添加策略成功回调
}

/**
 * 帖子互动按钮组
 *
 * @example
 * ```tsx
 * <PostActions
 *   post={fullPostData}
 *   postId={123}
 *   postTitle="我的策略"
 *   likes={42}
 *   comments={10}
 *   collections={5}
 *   isLiked={false}
 *   isCollected={true}
 *   showAddStrategyButton={true}
 *   onCommentClick={() => {}}
 * />
 * ```
 */
export const PostActions: React.FC<PostActionsProps> = ({
  post,
  postId,
  postTitle,
  likes,
  comments,
  collections = 0,
  isLiked = false,
  isCollected = false,
  size = 'medium',
  showCommentButton = true,
  showCollectButton = true,
  showShareButton = true,
  showAddStrategyButton = true,
  onCommentClick,
  onLikeChange,
  onCollectChange,
  onAddStrategySuccess,
}) => {
  const handleCommentClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCommentClick?.();
  };

  const buttonGroupClass = [
    'qm-interact-buttons',
    `qm-interact-buttons--${size}`,
  ].join(' ');

  return (
    <div className={buttonGroupClass}>
      {/* 点赞按钮 */}
      <LikeButton
        postId={postId}
        initialLiked={isLiked}
        initialLikes={likes}
        size={size}
        onLikeChange={onLikeChange}
      />

      {/* 评论按钮 */}
      {showCommentButton && (
        <Tooltip title="评论">
          <button
            className={`qm-interact-button qm-interact-button--${size}`}
            onClick={handleCommentClick}
            type="button"
            aria-label="评论"
          >
            <MessageOutlined className="qm-interact-button__icon" />
            <span className="qm-interact-button__count">{comments}</span>
          </button>
        </Tooltip>
      )}

      {/* 收藏按钮 */}
      {showCollectButton && (
        <CollectButton
          postId={postId}
          initialCollected={isCollected}
          initialCollections={collections}
          size={size}
          onCollectChange={onCollectChange}
        />
      )}

      {/* 分享按钮 */}
      {showShareButton && (
        <ShareButton
          postId={postId}
          postTitle={postTitle}
          size={size}
        />
      )}

      {/* 添加到我的策略按钮 */}
      {showAddStrategyButton && post && (
        <AddStrategyButton
          post={post}
          size={size}
          onAddSuccess={onAddStrategySuccess}
        />
      )}
    </div>
  );
};
