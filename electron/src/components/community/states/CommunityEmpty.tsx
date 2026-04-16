/**
 * 社区空状态组件
 *
 * 在没有数据时显示
 */

import React from 'react';
import { Empty, Button } from 'antd';
import { PlusOutlined, SearchOutlined, FileTextOutlined } from '@ant-design/icons';

interface CommunityEmptyProps {
  type?: 'no-posts' | 'no-search-results' | 'no-collections' | 'no-drafts';
  onAction?: () => void;
}

export const CommunityEmpty: React.FC<CommunityEmptyProps> = ({
  type = 'no-posts',
  onAction
}) => {
  // 根据类型返回不同的空状态配置
  const getEmptyConfig = () => {
    switch (type) {
      case 'no-posts':
        return {
          icon: <FileTextOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />,
          description: '暂无帖子',
          actionText: '发布第一篇帖子',
          actionIcon: <PlusOutlined />,
        };

      case 'no-search-results':
        return {
          icon: <SearchOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />,
          description: '没有找到相关内容',
          subDescription: '试试其他关键词或筛选条件',
          actionText: null,
          actionIcon: null,
        };

      case 'no-collections':
        return {
          icon: null,
          description: '还没有收藏任何帖子',
          subDescription: '去发现感兴趣的内容吧',
          actionText: '去浏览',
          actionIcon: null,
        };

      case 'no-drafts':
        return {
          icon: null,
          description: '暂无草稿',
          subDescription: '开始创作你的第一篇帖子',
          actionText: '开始写作',
          actionIcon: <PlusOutlined />,
        };

      default:
        return {
          icon: null,
          description: '暂无内容',
          actionText: null,
          actionIcon: null,
        };
    }
  };

  const config = getEmptyConfig();

  return (
    <div style={{
      padding: '60px 20px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '400px'
    }}>
      <Empty
        image={config.icon || Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div>
            <p style={{ fontSize: '16px', color: '#595959', margin: '8px 0' }}>
              {config.description}
            </p>
            {config.subDescription && (
              <p style={{ fontSize: '14px', color: '#8c8c8c', margin: '4px 0' }}>
                {config.subDescription}
              </p>
            )}
          </div>
        }
      >
        {config.actionText && onAction && (
          <Button
            type="primary"
            icon={config.actionIcon}
            onClick={onAction}
          >
            {config.actionText}
          </Button>
        )}
      </Empty>
    </div>
  );
};

/**
 * 简化版空状态（用于卡片内部）
 */
interface CommunityEmptyInlineProps {
  message: string;
}

export const CommunityEmptyInline: React.FC<CommunityEmptyInlineProps> = ({
  message,
}) => {
  return (
    <div
      style={{
        padding: '40px 20px',
        textAlign: 'center',
        color: '#8c8c8c',
      }}
    >
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={message}
      />
    </div>
  );
};
