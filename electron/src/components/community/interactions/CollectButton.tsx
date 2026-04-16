/**
 * 收藏按钮组件
 *
 * 可交互的收藏按钮
 */

import React, { useState, useCallback } from 'react';
import { StarOutlined, StarFilled } from '@ant-design/icons';
import { Tooltip, message } from 'antd';
import { communityService } from '../../../services/communityService';
import './InteractionButtons.css';

export interface CollectButtonProps {
  postId: number;
  initialCollected?: boolean;
  initialCollections?: number;
  size?: 'small' | 'medium' | 'large';
  showCount?: boolean;
  disabled?: boolean;
  onCollectChange?: (isCollected: boolean, collections: number) => void;
}

export const CollectButton: React.FC<CollectButtonProps> = ({
  postId,
  initialCollected = false,
  initialCollections = 0,
  size = 'medium',
  showCount = true,
  disabled = false,
  onCollectChange,
}) => {
  const [isCollected, setIsCollected] = useState(initialCollected);
  const [collections, setCollections] = useState(initialCollections);
  const [isLoading, setIsLoading] = useState(false);

  const toggleCollect = useCallback(async () => {
    if (isLoading || disabled) return;

    // 乐观更新
    const previousCollected = isCollected;
    const previousCollections = collections;
    const newCollected = !isCollected;
    const newCollections = newCollected ? collections + 1 : collections - 1;

    setIsCollected(newCollected);
    setCollections(newCollections);
    setIsLoading(true);

    try {
      const response = await communityService.toggleCollect({
        postId,
        isCollected: newCollected,
      });

      if (response) {
        setIsCollected(response.isCollected);
        setCollections(response.collections);
        message.success(newCollected ? '收藏成功' : '取消收藏');
        onCollectChange?.(response.isCollected, response.collections);
      } else {
        throw new Error('操作失败');
      }
    } catch (error) {
      console.error('CollectButton: toggleCollect error', error);
      setIsCollected(previousCollected);
      setCollections(previousCollections);

      const errorObj = error instanceof Error ? error : new Error('未知错误');
      message.error(errorObj.message);
    } finally {
      setIsLoading(false);
    }
  }, [postId, isCollected, collections, isLoading, disabled, onCollectChange]);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleCollect();
  };

  const buttonClass = [
    'qm-interact-button',
    `qm-interact-button--${size}`,
    isCollected && 'qm-interact-button--active',
    isLoading && 'qm-interact-button--loading',
    disabled && 'qm-interact-button--disabled',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Tooltip title={isCollected ? '取消收藏' : '收藏'}>
      <button
        className={buttonClass}
        onClick={handleClick}
        disabled={disabled || isLoading}
        type="button"
        aria-label={isCollected ? '取消收藏' : '收藏'}
        aria-pressed={isCollected}
      >
        {isCollected ? (
          <StarFilled className="qm-interact-button__icon qm-interact-button__icon--active" />
        ) : (
          <StarOutlined className="qm-interact-button__icon" />
        )}
        {showCount && <span className="qm-interact-button__count">{collections}</span>}
      </button>
    </Tooltip>
  );
};
