/**
 * 分享按钮组件
 *
 * 支持复制链接、分享到外部
 */

import React, { useState } from 'react';
import { ShareAltOutlined } from '@ant-design/icons';
import { Tooltip, message, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import './InteractionButtons.css';

export interface ShareButtonProps {
  postId: number;
  postTitle: string;
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
}

export const ShareButton: React.FC<ShareButtonProps> = ({
  postId,
  postTitle,
  size = 'medium',
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const buildShareUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set('communityPostId', String(postId));
    return url.toString();
  };

  const handleCopyLink = () => {
    const url = buildShareUrl();

    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(() => {
        message.success('链接已复制到剪贴板');
        setIsOpen(false);
      }).catch(() => {
        message.error('复制失败，请手动复制');
      });
    } else {
      // 降级方案
      const textArea = document.createElement('textarea');
      textArea.value = url;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        message.success('链接已复制到剪贴板');
        setIsOpen(false);
      } catch (err) {
        message.error('复制失败，请手动复制');
      }
      document.body.removeChild(textArea);
    }
  };

  const handleShareToWeChat = () => {
    message.info('微信分享功能开发中');
    setIsOpen(false);
  };

  const handleShareToWeibo = () => {
    const url = buildShareUrl();
    const weiboUrl = `https://service.weibo.com/share/share.php?url=${encodeURIComponent(url)}&title=${encodeURIComponent(postTitle)}`;
    window.open(weiboUrl, '_blank');
    setIsOpen(false);
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'copy-link',
      label: '复制链接',
      onClick: handleCopyLink,
    },
    {
      key: 'wechat',
      label: '分享到微信',
      onClick: handleShareToWeChat,
    },
    {
      key: 'weibo',
      label: '分享到微博',
      onClick: handleShareToWeibo,
    },
  ];

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  const buttonClass = [
    'qm-interact-button',
    `qm-interact-button--${size}`,
    disabled && 'qm-interact-button--disabled',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      open={isOpen}
      onOpenChange={setIsOpen}
      disabled={disabled}
    >
      <Tooltip title="分享">
        <button
          className={buttonClass}
          onClick={handleClick}
          disabled={disabled}
          type="button"
          aria-label="分享"
        >
          <ShareAltOutlined className="qm-interact-button__icon" />
        </button>
      </Tooltip>
    </Dropdown>
  );
};
