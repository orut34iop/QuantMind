/**
 * 评论输入框组件
 *
 * 支持Emoji、字数限制、取消/提交
 */

import React, { useState, useRef, useEffect } from 'react';
import { Button, message } from 'antd';
import { SmileOutlined } from '@ant-design/icons';
import type { CommentInputProps } from './types';
import './CommentInput.css';

const EMOJI_LIST = ['😀', '😃', '😄', '😁', '😅', '😂', '🤣', '😊', '😇', '🙂',
  '😍', '🥰', '😘', '😗', '😙', '😚', '😋', '😛', '😝', '😜', '🤪', '🤨', '🧐', '🤓',
  '👍', '👎', '👏', '🙏', '💪', '🎉', '🎊', '🚀', '⭐', '✨', '💯', '🔥'];

export const CommentInput: React.FC<CommentInputProps> = ({
  postId,
  parentId,
  replyTo,
  placeholder = '写下你的评论...',
  maxLength = 500,
  autoFocus = false,
  onSubmit,
  onCancel,
}) => {
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const emojiRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [autoFocus]);

  // 点击外部关闭Emoji面板
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (emojiRef.current && !emojiRef.current.contains(event.target as Node)) {
        setShowEmoji(false);
      }
    };

    if (showEmoji) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showEmoji]);

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    if (newContent.length <= maxLength) {
      setContent(newContent);
    }
  };

  const handleEmojiClick = (emoji: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const newContent = content.slice(0, start) + emoji + content.slice(end);

    if (newContent.length <= maxLength) {
      setContent(newContent);
      // 恢复光标位置
      setTimeout(() => {
        textarea.focus();
        textarea.setSelectionRange(start + emoji.length, start + emoji.length);
      }, 0);
    }
  };

  const handleSubmit = async () => {
    const trimmedContent = content.trim();

    if (!trimmedContent) {
      message.warning('请输入评论内容');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(trimmedContent);
      setContent('');
      message.success('评论成功');
    } catch (error) {
      message.error('评论失败，请重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setContent('');
    setShowEmoji(false);
    onCancel?.();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter 提交
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  const remainingChars = maxLength - content.length;
  const isOverLimit = remainingChars < 0;

  return (
    <div className="qm-comment-input">
      {replyTo && (
        <div className="qm-comment-input-reply-to">
          回复 <span className="qm-comment-input-reply-to-name">@{replyTo.name}</span>
        </div>
      )}

      <div className="qm-comment-input-wrapper">
        <textarea
          ref={textareaRef}
          className="qm-comment-input-textarea"
          placeholder={placeholder}
          value={content}
          onChange={handleContentChange}
          onKeyDown={handleKeyDown}
          rows={4}
          disabled={isSubmitting}
        />

        <div className="qm-comment-input-footer">
          <div className="qm-comment-input-tools">
            <div className="qm-comment-emoji-wrapper" ref={emojiRef}>
              <Button
                type="text"
                icon={<SmileOutlined />}
                onClick={() => setShowEmoji(!showEmoji)}
                className="qm-comment-emoji-btn"
                disabled={isSubmitting}
              />

              {showEmoji && (
                <div className="qm-comment-emoji-picker">
                  <div className="qm-comment-emoji-list">
                    {EMOJI_LIST.map((emoji) => (
                      <button
                        key={emoji}
                        className="qm-comment-emoji-item"
                        onClick={() => handleEmojiClick(emoji)}
                        type="button"
                      >
                        {emoji}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className={`qm-comment-input-count ${isOverLimit ? 'qm-comment-input-count--over' : ''}`}>
              {remainingChars}
            </div>
          </div>

          <div className="qm-comment-input-actions">
            {onCancel && (
              <Button
                onClick={handleCancel}
                disabled={isSubmitting}
              >
                取消
              </Button>
            )}
            <Button
              type="primary"
              onClick={handleSubmit}
              loading={isSubmitting}
              disabled={!content.trim() || isOverLimit}
            >
              {isSubmitting ? '提交中...' : '发表评论'}
            </Button>
          </div>
        </div>
      </div>

      <div className="qm-comment-input-tip">
        按 Ctrl + Enter 快速发表
      </div>
    </div>
  );
};
