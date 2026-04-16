/**
 * 发帖弹窗主容器
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState, useEffect } from 'react';
import { Modal, Input, Form, Button, Space, message, Tabs } from 'antd';
import { SaveOutlined, EyeOutlined, FileTextOutlined, PictureOutlined } from '@ant-design/icons';
import CategorySelector from './CategorySelector';
import TagSelector from './TagSelector';
import { PostEditor } from './PostEditor';
import { MediaUploader } from './MediaUploader';
import type { MediaFile } from './MediaUploader';
import './post-creation.css';

export interface PostFormData {
  title: string;
  content: string;
  category: string;
  tags: string[];
  thumbnail?: string;
  mediaFiles?: MediaFile[];
}

export interface PostCreationModalProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (data: PostFormData) => Promise<void>;
  initialData?: Partial<PostFormData>;
}

const DRAFT_KEY = 'community_post_draft';

export const PostCreationModal: React.FC<PostCreationModalProps> = ({
  visible,
  onCancel,
  onSubmit,
  initialData
}) => {
  const [form] = Form.useForm();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);

  useEffect(() => {
    if (visible) {
      const savedDraft = localStorage.getItem(DRAFT_KEY);
      if (savedDraft && !initialData) {
        try {
          const draft = JSON.parse(savedDraft);
          form.setFieldsValue(draft);
          setHasChanges(true);
        } catch {
          // 忽略解析错误
        }
      } else if (initialData) {
        form.setFieldsValue(initialData);
      }
    }
  }, [visible, initialData, form]);

  useEffect(() => {
    if (hasChanges && visible) {
      const timer = setTimeout(() => {
        const values = form.getFieldsValue();
        localStorage.setItem(DRAFT_KEY, JSON.stringify(values));
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [hasChanges, visible, form]);

  const handleCancel = () => {
    if (hasChanges) {
      Modal.confirm({
        title: '确认关闭？',
        content: '您有未保存的内容，确定要关闭吗？',
        okText: '保存草稿并关闭',
        cancelText: '直接关闭',
        onOk: () => {
          const values = form.getFieldsValue();
          localStorage.setItem(DRAFT_KEY, JSON.stringify(values));
          form.resetFields();
          setHasChanges(false);
          onCancel();
        },
        onCancel: () => {
          localStorage.removeItem(DRAFT_KEY);
          form.resetFields();
          setHasChanges(false);
          onCancel();
        }
      });
    } else {
      form.resetFields();
      onCancel();
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setIsSubmitting(true);

      await onSubmit(values as PostFormData);

      localStorage.removeItem(DRAFT_KEY);
      form.resetFields();
      setHasChanges(false);
      message.success('发布成功！');
    } catch (error) {
      if (error instanceof Error) {
        message.error(error.message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePreview = () => {
    form.validateFields(['title', 'content', 'category']).then((values) => {
      setPreviewVisible(true);
    }).catch(() => {
      message.warning('请先填写标题、分类和内容');
    });
  };

  const handleValuesChange = () => {
    setHasChanges(true);
  };

  const formValues = Form.useWatch([], form);

  return (
    <Modal
      title="发表新帖"
      open={visible}
      onCancel={handleCancel}
      width={900}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          取消
        </Button>,
        <Button key="preview" icon={<EyeOutlined />} onClick={handlePreview}>
          预览
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={isSubmitting}
          onClick={handleSubmit}
        >
          发布
        </Button>
      ]}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        onValuesChange={handleValuesChange}
      >
        <Form.Item
          label="标题"
          name="title"
          rules={[
            { required: true, message: '请输入标题' },
            { max: 100, message: '标题不能超过100个字符' }
          ]}
        >
          <Input
            placeholder="请输入标题（100字以内）"
            showCount
            maxLength={100}
          />
        </Form.Item>

        <Form.Item
          label="分类"
          name="category"
          rules={[{ required: true, message: '请选择分类' }]}
        >
          <CategorySelector />
        </Form.Item>

        <Tabs
          defaultActiveKey="content"
          items={[
            {
              key: 'content',
              label: (
                <span>
                  <FileTextOutlined />
                  正文内容
                </span>
              ),
              children: (
                <Form.Item
                  name="content"
                  rules={[
                    { required: true, message: '请输入内容' },
                    {
                      validator: (_, value) => {
                        const temp = document.createElement('div');
                        temp.innerHTML = value || '';
                        const textLength = (temp.textContent || '').length;
                        if (textLength < 50) {
                          return Promise.reject('内容至少需要50个字符');
                        }
                        return Promise.resolve();
                      }
                    }
                  ]}
                >
                  <PostEditor
                    placeholder="分享你的策略、经验或见解..."
                    maxLength={50000}
                    minLength={50}
                  />
                </Form.Item>
              )
            },
            {
              key: 'media',
              label: (
                <span>
                  <PictureOutlined />
                  图片/视频/附件
                </span>
              ),
              children: (
                <Form.Item
                  name="mediaFiles"
                  label="上传媒体文件（可选）"
                >
                  <MediaUploader
                    maxImages={9}
                    maxVideos={1}
                    maxAttachments={3}
                  />
                </Form.Item>
              )
            }
          ]}
        />

        <Form.Item
          label="标签"
          name="tags"
          rules={[
            { required: true, message: '请至少选择一个标签' },
            {
              validator: (_, value) => {
                if (!value || value.length === 0) {
                  return Promise.reject('请至少选择一个标签');
                }
                return Promise.resolve();
              }
            }
          ]}
        >
          <TagSelector maxTags={5} />
        </Form.Item>
      </Form>

      {hasChanges && (
        <div className="draft-save-hint">
          <SaveOutlined /> 草稿将自动保存
        </div>
      )}

      {/* 预览弹窗 */}
      <Modal
        title="预览帖子"
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={800}
      >
        <div className="post-preview">
          <h2 className="text-xl font-bold mb-4">{formValues?.title || '无标题'}</h2>
          <div className="text-sm text-gray-500 mb-2">
            分类：{formValues?.category || '未选择'}
          </div>
          {formValues?.tags && formValues.tags.length > 0 && (
            <div className="flex gap-2 mb-4">
              {formValues.tags.map((tag: string) => (
                <span key={tag} className="px-2 py-1 bg-blue-50 text-blue-600 rounded text-xs">
                  {tag}
                </span>
              ))}
            </div>
          )}
          <div 
            className="prose max-w-none"
            dangerouslySetInnerHTML={{ __html: formValues?.content || '' }}
          />
        </div>
      </Modal>
    </Modal>
  );
};

export default PostCreationModal;
