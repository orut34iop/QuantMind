/**
 * 标签选择器组件
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState, useRef, useEffect } from 'react';
import { Tag, Input, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import './post-creation.css';

export interface TagSelectorProps {
  value?: string[];
  onChange?: (tags: string[]) => void;
  maxTags?: number;
  hotTags?: string[];
  placeholder?: string;
  disabled?: boolean;
}

const DEFAULT_HOT_TAGS = [
  '量化策略', '回测', '机器学习', 'Python', 'A股', '期货',
  '因子分析', '风险管理', '数据分析', 'CTA策略'
];

export const TagSelector: React.FC<TagSelectorProps> = ({
  value = [],
  onChange,
  maxTags = 5,
  hotTags = DEFAULT_HOT_TAGS,
  placeholder = '添加标签',
  disabled = false
}) => {
  const [inputVisible, setInputVisible] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<any>(null);

  useEffect(() => {
    if (inputVisible) {
      inputRef.current?.focus();
    }
  }, [inputVisible]);

  const handleRemove = (removedTag: string) => {
    const newTags = value.filter(tag => tag !== removedTag);
    onChange?.(newTags);
  };

  const handleInputConfirm = () => {
    const trimmedValue = inputValue.trim();
    if (trimmedValue && !value.includes(trimmedValue) && value.length < maxTags) {
      onChange?.([...value, trimmedValue]);
    }
    setInputVisible(false);
    setInputValue('');
  };

  const handleAddTag = (tag: string) => {
    if (!value.includes(tag) && value.length < maxTags) {
      onChange?.([...value, tag]);
    }
  };

  return (
    <div className="tag-selector">
      <div className="selected-tags">
        <Space size={[0, 8]} wrap>
          {value.map(tag => (
            <Tag
              key={tag}
              closable={!disabled}
              onClose={() => handleRemove(tag)}
              style={{ marginRight: 3 }}
            >
              {tag}
            </Tag>
          ))}
          {value.length < maxTags && !disabled && (
            inputVisible ? (
              <Input
                ref={inputRef}
                type="text"
                size="small"
                style={{ width: 100 }}
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onBlur={handleInputConfirm}
                onPressEnter={handleInputConfirm}
                placeholder={placeholder}
              />
            ) : (
              <Tag
                onClick={() => setInputVisible(true)}
                style={{ background: '#fff', borderStyle: 'dashed', cursor: 'pointer' }}
              >
                <PlusOutlined /> 添加标签
              </Tag>
            )
          )}
        </Space>
        {value.length >= maxTags && (
          <span className="tag-limit-hint">已达到标签数量上限</span>
        )}
      </div>

      {hotTags.length > 0 && (
        <div className="hot-tags">
          <span className="label">热门标签：</span>
          <Space size={[0, 8]} wrap>
            {hotTags.map(tag => (
              <Tag
                key={tag}
                onClick={() => !disabled && handleAddTag(tag)}
                style={{
                  cursor: disabled || value.includes(tag) ? 'not-allowed' : 'pointer',
                  opacity: value.includes(tag) ? 0.5 : 1
                }}
              >
                {tag}
              </Tag>
            ))}
          </Space>
        </div>
      )}
    </div>
  );
};

export default TagSelector;
