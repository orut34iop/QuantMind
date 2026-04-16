/**
 * 评论列表组件
 *
 * 显示评论列表，支持加载更多、骨架屏
 */

import React from 'react';
import { Button, Empty, Skeleton } from 'antd';
import { CommentItem } from './CommentItem';
import type { CommentListProps } from './types';
import './CommentList.css';

export const CommentList: React.FC<CommentListProps> = ({
  postId,
  comments,
  loading = false,
  hasMore = false,
  currentUserId,
  onLoadMore,
  onReply,
  onDelete,
}) => {
  // 骨架屏
  if (loading && comments.length === 0) {
    return (
      <div className="qm-comment-list">
        <div className="qm-comment-list-header">
          <h3>评论</h3>
        </div>
        <div className="qm-comment-list-loading">
          {[1, 2, 3].map((i) => (
            <div key={i} className="qm-comment-skeleton">
              <Skeleton.Avatar active size={40} />
              <div className="qm-comment-skeleton-content">
                <Skeleton active paragraph={{ rows: 2 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 空状态
  if (!loading && comments.length === 0) {
    return (
      <div className="qm-comment-list">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无评论，快来抢沙发吧~"
          className="qm-comment-empty"
        />
      </div>
    );
  }

  return (
    <div className="qm-comment-list">
      <div className="qm-comment-list-content">
        {comments.map((comment) => (
          <CommentItem
            key={comment.id}
            comment={comment}
            currentUserId={currentUserId}
            showReplies={true}
            onReply={onReply}
            onDelete={onDelete}
          />
        ))}
      </div>

      {/* 加载更多 */}
      {hasMore && (
        <div className="qm-comment-load-more">
          <Button
            type="default"
            loading={loading}
            onClick={onLoadMore}
            block
          >
            {loading ? '加载中...' : '加载更多评论'}
          </Button>
        </div>
      )}

      {/* 底部加载中 */}
      {loading && comments.length > 0 && (
        <div className="qm-comment-loading-more">
          <Skeleton active paragraph={{ rows: 1 }} />
        </div>
      )}
    </div>
  );
};
