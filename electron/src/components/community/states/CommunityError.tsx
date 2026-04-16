/**
 * 社区错误提示组件
 *
 * 在数据加载失败时显示，提供重试功能
 */

import React from 'react';
import { Button, Result } from 'antd';
import { ReloadOutlined, ApiOutlined, DisconnectOutlined } from '@ant-design/icons';

interface CommunityErrorProps {
  error: Error | string;
  onRetry?: () => void;
  type?: 'network' | 'api' | 'unknown';
}

export const CommunityError: React.FC<CommunityErrorProps> = ({
  error,
  onRetry,
  type = 'unknown'
}) => {
  // 解析错误信息
  const errorMessage = typeof error === 'string' ? error : error.message;

  // 根据错误类型选择图标和文案
  const getErrorConfig = () => {
    if (type === 'network') {
      return {
        icon: <DisconnectOutlined style={{ fontSize: 64, color: '#ff4d4f' }} />,
        title: '网络连接失败',
        subTitle: '请检查您的网络连接后重试',
      };
    }

    if (type === 'api') {
      return {
        icon: <ApiOutlined style={{ fontSize: 64, color: '#faad14' }} />,
        title: 'API 请求失败',
        subTitle: errorMessage || '服务暂时不可用，请稍后重试',
      };
    }

    return {
      icon: undefined,
      title: '加载失败',
      subTitle: errorMessage || '发生了未知错误，请重试',
    };
  };

  const config = getErrorConfig();

  return (
    <div style={{
      padding: '40px 20px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '400px'
    }}>
      <Result
        status="error"
        icon={config.icon}
        title={config.title}
        subTitle={config.subTitle}
        extra={[
          onRetry && (
            <Button
              key="retry"
              type="primary"
              icon={<ReloadOutlined />}
              onClick={onRetry}
            >
              重新加载
            </Button>
          ),
        ]}
      />
    </div>
  );
};

/**
 * 简化版错误提示（用于卡片内部）
 */
interface CommunityErrorInlineProps {
  message: string;
  onRetry?: () => void;
}

export const CommunityErrorInline: React.FC<CommunityErrorInlineProps> = ({
  message,
  onRetry,
}) => {
  return (
    <div
      style={{
        padding: '20px',
        textAlign: 'center',
        backgroundColor: '#fff2e8',
        borderRadius: '8px',
        border: '1px solid #ffbb96',
      }}
    >
      <p style={{ color: '#d4380d', margin: '0 0 12px 0' }}>{message}</p>
      {onRetry && (
        <Button size="small" onClick={onRetry} icon={<ReloadOutlined />}>
          重试
        </Button>
      )}
    </div>
  );
};
