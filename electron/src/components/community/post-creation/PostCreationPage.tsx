/**
 * 帖子创建/编辑页面
 *
 * 集成富文本编辑器、图片上传、标签选择等功能
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState, useCallback, useEffect } from 'react';
import { EnhancedPostEditor } from './EnhancedPostEditor';
import { FileUpload } from '../../ui/FileUpload';
import { Save, Eye, X, Tag, AlertCircle } from 'lucide-react';

export interface PostFormData {
  title: string;
  content: string;
  tags: string[];
  category: string;
  attachments?: string[];
}

export interface PostCreationPageProps {
  initialData?: PostFormData;
  onSave: (data: PostFormData) => Promise<void>;
  onCancel: () => void;
  mode?: 'create' | 'edit';
}

const CATEGORIES = [
  { value: 'strategy', label: '策略分享' },
  { value: 'discussion', label: '技术讨论' },
  { value: 'question', label: '问题求助' },
  { value: 'news', label: '市场资讯' },
  { value: 'tutorial', label: '教程分享' },
  { value: 'other', label: '其他' },
];

const COMMON_TAGS = [
  '量化策略',
  '技术分析',
  '基本面分析',
  '回测',
  'Python',
  '机器学习',
  '股票',
  '期货',
  '数字货币',
  '风险管理',
  'A股',
  '美股',
];

export const PostCreationPage: React.FC<PostCreationPageProps> = ({
  initialData,
  onSave,
  onCancel,
  mode = 'create',
}) => {
  const [formData, setFormData] = useState<PostFormData>(
    initialData || {
      title: '',
      content: '',
      tags: [],
      category: 'discussion',
      attachments: [],
    }
  );

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [customTag, setCustomTag] = useState('');
  const [showTagInput, setShowTagInput] = useState(false);

  // 表单验证
  const validate = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    // 标题验证
    if (!formData.title.trim()) {
      newErrors.title = '请输入标题';
    } else if (formData.title.length < 5) {
      newErrors.title = '标题至少需要5个字符';
    } else if (formData.title.length > 100) {
      newErrors.title = '标题不能超过100个字符';
    }

    // 内容验证
    const textContent = formData.content.replace(/<[^>]*>/g, '').trim();
    if (!textContent) {
      newErrors.content = '请输入内容';
    } else if (textContent.length < 50) {
      newErrors.content = '内容至少需要50个字符';
    }

    // 分类验证
    if (!formData.category) {
      newErrors.category = '请选择分类';
    }

    // 标签验证
    if (formData.tags.length === 0) {
      newErrors.tags = '请至少选择一个标签';
    } else if (formData.tags.length > 5) {
      newErrors.tags = '最多只能选择5个标签';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  // 保存帖子
  const handleSave = useCallback(async () => {
    if (!validate()) {
      return;
    }

    setSaving(true);
    try {
      await onSave(formData);
    } catch (error) {
      console.error('保存失败:', error);
      setErrors({ submit: error instanceof Error ? error.message : '保存失败' });
    } finally {
      setSaving(false);
    }
  }, [formData, validate, onSave]);

  // 更新表单字段
  const updateField = useCallback(<K extends keyof PostFormData>(
    field: K,
    value: PostFormData[K]
  ) => {
    (setFormData as any)(prev => ({ ...prev, [field]: value }));
    // 清除该字段的错误
    if (errors[field]) {
      (setErrors as any)(prev => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  }, [errors]);

  // 添加标签
  const addTag = useCallback((tag: string) => {
    if (!tag.trim()) return;

    if (formData.tags.length >= 5) {
      (setErrors as any)(prev => ({ ...prev, tags: '最多只能选择5个标签' }));
      return;
    }

    if (formData.tags.includes(tag)) {
      return;
    }

    updateField('tags', [...formData.tags, tag]);
    setCustomTag('');
    setShowTagInput(false);
  }, [formData.tags, updateField]);

  // 移除标签
  const removeTag = useCallback((tag: string) => {
    updateField('tags', formData.tags.filter(t => t !== tag));
  }, [formData.tags, updateField]);

  // 处理附件上传完成
  const handleAttachmentUpload = useCallback((files: any[]) => {
    const fileUrls = files.map(f => f.url);
    updateField('attachments', [...(formData.attachments || []), ...fileUrls]);
  }, [formData.attachments, updateField]);

  return (
    <div className="max-w-5xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b">
        <h1 className="text-2xl font-bold text-gray-900">
          {mode === 'create' ? '发布新帖' : '编辑帖子'}
        </h1>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center space-x-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Eye className="w-4 h-4" />
            <span>{showPreview ? '编辑' : '预览'}</span>
          </button>
          <button
            onClick={onCancel}
            className="flex items-center space-x-2 px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <X className="w-4 h-4" />
            <span>取消</span>
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center space-x-2 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? '保存中...' : '发布'}</span>
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {errors.submit && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start space-x-2">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-red-800">{errors.submit}</p>
          </div>
        </div>
      )}

      {showPreview ? (
        /* 预览模式 */
        <div className="space-y-6">
          <div>
            <h2 className="text-3xl font-bold text-gray-900 mb-4">{formData.title}</h2>
            <div className="flex items-center space-x-4 text-sm text-gray-600 mb-4">
              <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full">
                {CATEGORIES.find(c => c.value === formData.category)?.label}
              </span>
              {formData.tags.map(tag => (
                <span key={tag} className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full">
                  #{tag}
                </span>
              ))}
            </div>
          </div>

          <div
            className="prose max-w-none"
            dangerouslySetInnerHTML={{ __html: formData.content }}
          />

          {formData.attachments && formData.attachments.length > 0 && (
            <div className="pt-6 border-t">
              <h3 className="text-lg font-semibold mb-3">附件</h3>
              <div className="space-y-2">
                {formData.attachments.map((url, index) => (
                  <a
                    key={index}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    附件 {index + 1}
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* 编辑模式 */
        <div className="space-y-6">
          {/* 标题 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              标题 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="请输入帖子标题（5-100字符）"
              className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.title ? 'border-red-500' : 'border-gray-300'
              }`}
              maxLength={100}
            />
            {errors.title && (
              <p className="mt-1 text-sm text-red-600">{errors.title}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              {formData.title.length} / 100 字符
            </p>
          </div>

          {/* 分类 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              分类 <span className="text-red-500">*</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map(cat => (
                <button
                  key={cat.value}
                  onClick={() => updateField('category', cat.value)}
                  className={`px-4 py-2 rounded-lg border transition-colors ${
                    formData.category === cat.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:border-blue-500'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
            {errors.category && (
              <p className="mt-1 text-sm text-red-600">{errors.category}</p>
            )}
          </div>

          {/* 标签 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              标签 <span className="text-red-500">*</span>
              <span className="ml-2 text-xs text-gray-500">
                (最少1个，最多5个)
              </span>
            </label>

            {/* 已选标签 */}
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {formData.tags.map(tag => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full"
                  >
                    <Tag className="w-3 h-3 mr-1" />
                    {tag}
                    <button
                      onClick={() => removeTag(tag)}
                      className="ml-2 text-blue-600 hover:text-blue-800"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* 常用标签 */}
            <div className="flex flex-wrap gap-2 mb-3">
              {COMMON_TAGS.filter(tag => !formData.tags.includes(tag)).map(tag => (
                <button
                  key={tag}
                  onClick={() => addTag(tag)}
                  disabled={formData.tags.length >= 5}
                  className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  + {tag}
                </button>
              ))}
            </div>

            {/* 自定义标签输入 */}
            {showTagInput ? (
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={customTag}
                  onChange={(e) => setCustomTag(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag(customTag);
                    }
                  }}
                  placeholder="输入自定义标签"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  maxLength={20}
                />
                <button
                  onClick={() => addTag(customTag)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  添加
                </button>
                <button
                  onClick={() => {
                    setShowTagInput(false);
                    setCustomTag('');
                  }}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowTagInput(true)}
                disabled={formData.tags.length >= 5}
                className="text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                + 添加自定义标签
              </button>
            )}

            {errors.tags && (
              <p className="mt-1 text-sm text-red-600">{errors.tags}</p>
            )}
          </div>

          {/* 内容编辑器 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              内容 <span className="text-red-500">*</span>
            </label>
            <EnhancedPostEditor
              value={formData.content}
              onChange={(content) => updateField('content', content)}
              placeholder="请输入帖子内容，支持富文本格式、图片上传..."
              minLength={50}
              maxLength={50000}
              onError={(error) => (setErrors as any)(prev => ({ ...prev, content: error }))}
              maxImageSize={10}
              maxImages={9}
            />
            {errors.content && (
              <p className="mt-1 text-sm text-red-600">{errors.content}</p>
            )}
          </div>

          {/* 附件上传 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              附件（可选）
            </label>
            <FileUpload
              category="document"
              multiple
              maxFiles={5}
              maxSize={50}
              accept=".pdf,.doc,.docx,.xls,.xlsx,.py,.ipynb,.zip"
              description="支持上传策略代码、回测报告、数据文件等"
              onUploadComplete={handleAttachmentUpload}
              onUploadError={(error) => (setErrors as any)(prev => ({ ...prev, attachments: error }))}
            />
            {errors.attachments && (
              <p className="mt-1 text-sm text-red-600">{errors.attachments}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PostCreationPage;
