/**
 * 社区加载骨架屏组件
 *
 * 在数据加载时显示，提升用户体验
 */

import React from 'react';
import { Skeleton } from 'antd';
import '../CommunityHub.css';

interface CommunityFeedSkeletonProps {
  count?: number;
}

export const CommunityFeedSkeleton: React.FC<CommunityFeedSkeletonProps> = ({
  count = 8
}) => {
  return (
    <div className="qm-community__feed">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="qm-community__post-card" style={{ marginBottom: '20px' }}>
          {/* 帖子头部 */}
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
            <Skeleton.Avatar active size="small" />
            <div style={{ marginLeft: '12px', flex: 1 }}>
              <Skeleton.Input active size="small" style={{ width: '100px', height: '16px' }} />
              <Skeleton.Input active size="small" style={{ width: '80px', height: '12px', marginTop: '4px' }} />
            </div>
          </div>

          {/* 标题 */}
          <Skeleton.Input
            active
            style={{ width: '80%', height: '24px', marginBottom: '8px' }}
          />

          {/* 摘要 */}
          <Skeleton
            active
            paragraph={{ rows: 2, width: ['100%', '60%'] }}
            title={false}
            style={{ marginBottom: '12px' }}
          />

          {/* 标签 */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <Skeleton.Button active size="small" style={{ width: '60px', height: '24px' }} />
            <Skeleton.Button active size="small" style={{ width: '60px', height: '24px' }} />
            <Skeleton.Button active size="small" style={{ width: '60px', height: '24px' }} />
          </div>

          {/* 底部统计 */}
          <div style={{ display: 'flex', gap: '16px' }}>
            <Skeleton.Input active size="small" style={{ width: '60px', height: '16px' }} />
            <Skeleton.Input active size="small" style={{ width: '60px', height: '16px' }} />
            <Skeleton.Input active size="small" style={{ width: '60px', height: '16px' }} />
          </div>
        </div>
      ))}
    </div>
  );
};

/**
 * 简化版骨架屏（用于列表加载更多）
 */
export const CommunityPostCardSkeleton: React.FC = () => {
  return (
    <div className="qm-community__post-card" style={{ marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
        <Skeleton.Avatar active size="small" />
        <div style={{ marginLeft: '12px', flex: 1 }}>
          <Skeleton.Input active size="small" style={{ width: '100px', height: '16px' }} />
        </div>
      </div>
      <Skeleton.Input active style={{ width: '70%', height: '20px', marginBottom: '8px' }} />
      <Skeleton active paragraph={{ rows: 1 }} title={false} />
    </div>
  );
};
