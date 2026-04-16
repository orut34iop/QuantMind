/**
 * 分类选择器组件
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React from 'react';
import { Radio, Space, RadioChangeEvent } from 'antd';
import './post-creation.css';

export interface Category {
  value: string;
  label: string;
  icon?: string;
  description?: string;
}

export interface CategorySelectorProps {
  value?: string;
  onChange?: (value: string) => void;
  categories?: Category[];
  disabled?: boolean;
}

const DEFAULT_CATEGORIES: Category[] = [
  { value: '研究交流', label: '研究交流', icon: '💬', description: '分享研究成果和经验交流' },
  { value: '策略', label: '策略', icon: '📊', description: '分享量化策略和交易思路' },
  { value: '问答', label: '问答', icon: '❓', description: '寻求帮助和问题解答' },
  { value: '文档', label: '文档', icon: '📚', description: '技术文档和教程指南' },
  { value: '课程', label: '课程', icon: '🎓', description: '学习量化投资的专业课程' },
  { value: '比赛', label: '比赛', icon: '🏆', description: '参与量化竞赛，挑战自我' },
  { value: '实盘', label: '实盘', icon: '💹', description: '实盘经验分享与交流' }
];

export const CategorySelector: React.FC<CategorySelectorProps> = ({
  value,
  onChange,
  categories = DEFAULT_CATEGORIES,
  disabled = false
}) => {
  const handleChange = (e: RadioChangeEvent) => {
    onChange?.(e.target.value);
  };

  return (
    <div className="category-selector">
      <Radio.Group
        value={value}
        onChange={handleChange}
        disabled={disabled}
        buttonStyle="solid"
      >
        <Space direction="horizontal" size={12} wrap>
          {categories.map(cat => (
            <Radio.Button
              key={cat.value}
              value={cat.value}
              title={cat.description}
            >
              {cat.icon && <span className="category-icon">{cat.icon}</span>}
              <span className="category-label">{cat.label}</span>
            </Radio.Button>
          ))}
        </Space>
      </Radio.Group>
    </div>
  );
};

export default CategorySelector;
