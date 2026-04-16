/**
 * 发帖按钮组件
 *
 * 悬浮在页面右下角的发帖入口按钮
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React from 'react';
import { FloatButton } from 'antd';
import { EditOutlined } from '@ant-design/icons';

export interface PostCreationButtonProps {
  onClick: () => void;
  tooltip?: string;
  type?: 'default' | 'primary';
  icon?: React.ReactNode;
}

export const PostCreationButton: React.FC<PostCreationButtonProps> = ({
  onClick,
  tooltip = '发表新帖',
  type = 'primary',
  icon
}) => {
  return (
    <FloatButton
      icon={icon || <EditOutlined />}
      type={type}
      tooltip={tooltip}
      onClick={onClick}
      style={{
        right: 24,
        bottom: 24,
      }}
    />
  );
};

export default PostCreationButton;
