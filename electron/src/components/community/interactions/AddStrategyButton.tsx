/**
 * 添加策略到个人中心按钮
 */

import React, { useState } from 'react';
import { PlusOutlined, CheckOutlined } from '@ant-design/icons';
import { Tooltip, message } from 'antd';
import type { CommunityPost } from '../types';
import './InteractionButtons.css';

export interface AddStrategyButtonProps {
  post: CommunityPost;
  size?: 'small' | 'medium' | 'large';
  onAddSuccess?: () => void;
}

/**
 * 添加策略到个人中心按钮
 * 只在帖子包含策略元数据时显示
 */
export const AddStrategyButton: React.FC<AddStrategyButtonProps> = ({
  post,
  size = 'medium',
  onAddSuccess,
}) => {
  const [isAdding, setIsAdding] = useState(false);
  const [isAdded, setIsAdded] = useState(false);

  // 如果帖子不包含策略元数据，不显示按钮
  if (!post.strategy_metadata) {
    return null;
  }

  const handleAddStrategy = async (e: React.MouseEvent) => {
    e.stopPropagation();

    if (isAdded) {
      message.info('该策略已添加到您的策略库');
      return;
    }

    setIsAdding(true);

    try {
      // 导入 userCenterService
      const { userCenterService } = await import('../../../features/user-center/services/userCenterService');

      // 构建策略数据
      const strategyData = {
        strategy_name: `[社区] ${post.title}`,
        strategy_type: post.strategy_metadata.strategy_type,
        description: post.excerpt || post.content?.substring(0, 200),
        config: post.strategy_metadata.config,
        tags: post.tags,
        notes: `来自社区用户：${post.author}\n原帖子ID：${post.id}`,
        source: 'community' as const,
        source_post_id: post.id,
        performance_summary: post.strategy_metadata.performance_summary,
      };

      console.log('添加策略到个人中心:', strategyData);

      // 调用API
      await userCenterService.importStrategyFromCommunity(strategyData);

      setIsAdded(true);
      message.success('已成功添加到我的策略库！');
      onAddSuccess?.();
    } catch (error: any) {
      console.error('添加策略失败:', error);
      message.error(error.message || '添加失败，请稍后重试');
    } finally {
      setIsAdding(false);
    }
  };

  const icon = isAdded ? <CheckOutlined /> : <PlusOutlined />;
  const text = isAdded ? '已添加' : '添加到我的策略';
  const tooltipTitle = isAdded ? '该策略已在您的策略库中' : '将此策略添加到我的策略库';

  return (
    <Tooltip title={tooltipTitle}>
      <button
        className={`qm-interact-button qm-interact-button--${size} ${isAdded ? 'qm-interact-button--added' : ''}`}
        onClick={handleAddStrategy}
        type="button"
        disabled={isAdding || isAdded}
        aria-label={text}
        style={{
          color: isAdded ? '#52c41a' : undefined,
          cursor: isAdded ? 'default' : 'pointer',
        }}
      >
        {icon}
        <span className="qm-interact-button__text">{text}</span>
      </button>
    </Tooltip>
  );
};

export default AddStrategyButton;
