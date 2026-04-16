/**
 * 点赞按钮组件
 *
 * 可交互的点赞按钮，支持动画效果
 */

import React from 'react';
import { HeartOutlined, HeartFilled } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useLike } from '../../../hooks/community/useLike';
import './LikeButton.css';

export interface LikeButtonProps {
  postId: number;
  initialLiked?: boolean;
  initialLikes?: number;
  size?: 'small' | 'medium' | 'large';
  showCount?: boolean;
  disabled?: boolean;
  onLikeChange?: (isLiked: boolean, likes: number) => void;
}

export const LikeButton: React.FC<LikeButtonProps> = ({
  postId,
  initialLiked = false,
  initialLikes = 0,
  size = 'medium',
  showCount = true,
  disabled = false,
  onLikeChange,
}) => {
  const { isLiked, likes, isLoading, toggleLike } = useLike({
    postId,
    initialLiked,
    initialLikes,
    onSuccess: (liked, count) => {
      onLikeChange?.(liked, count);
    },
  });

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // 防止触发父元素的点击事件
    if (!disabled && !isLoading) {
      toggleLike();
    }
  };

  const buttonClass = [
    'qm-like-button',
    `qm-like-button--${size}`,
    isLiked && 'qm-like-button--liked',
    isLoading && 'qm-like-button--loading',
    disabled && 'qm-like-button--disabled',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Tooltip title={isLiked ? '取消点赞' : '点赞'}>
      <button
        className={buttonClass}
        onClick={handleClick}
        disabled={disabled || isLoading}
        type="button"
        aria-label={isLiked ? '取消点赞' : '点赞'}
        aria-pressed={isLiked}
      >
        {isLiked ? (
          <HeartFilled className="qm-like-button__icon qm-like-button__icon--active" />
        ) : (
          <HeartOutlined className="qm-like-button__icon" />
        )}
        {showCount && <span className="qm-like-button__count">{likes}</span>}
      </button>
    </Tooltip>
  );
};

/**
 * 简化版点赞按钮（只显示图标）
 */
export const LikeButtonIcon: React.FC<
  Omit<LikeButtonProps, 'showCount'>
> = (props) => {
  return <LikeButton {...props} showCount={false} />;
};
