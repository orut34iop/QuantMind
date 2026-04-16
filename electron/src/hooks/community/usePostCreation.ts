/**
 * 发帖功能Hook
 *
 * 处理发帖的业务逻辑，包括表单验证、提交、草稿管理等
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import { useState, useCallback } from 'react';
import { message } from 'antd';
import { communityService } from '../../services/communityService';
import type { PostFormData } from '../../components/community/post-creation';

export interface UsePostCreationOptions {
  onSuccess?: (postId: number) => void;
  onError?: (error: Error) => void;
}

export interface UsePostCreationReturn {
  isSubmitting: boolean;
  errors: Record<string, string>;
  validateForm: (data: PostFormData) => boolean;
  submitPost: (data: PostFormData) => Promise<void>;
  clearErrors: () => void;
}

/**
 * 发帖Hook
 *
 * @param options 配置选项
 * @returns 发帖相关的状态和方法
 *
 * @example
 * ```tsx
 * const { isSubmitting, submitPost } = usePostCreation({
 *   onSuccess: (postId) => {
 *     console.log('Post created:', postId);
 *     refreshList();
 *   }
 * });
 *
 * await submitPost(formData);
 * ```
 */
export function usePostCreation(options: UsePostCreationOptions = {}): UsePostCreationReturn {
  const { onSuccess, onError } = options;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  /**
   * 表单验证
   */
  const validateForm = useCallback((data: PostFormData): boolean => {
    const newErrors: Record<string, string> = {};

    // 验证标题
    if (!data.title || !data.title.trim()) {
      newErrors.title = '请输入标题';
    } else if (data.title.length > 100) {
      newErrors.title = '标题不能超过100个字符';
    }

    // 验证内容
    if (!data.content || !data.content.trim()) {
      newErrors.content = '请输入内容';
    } else if (data.content.length < 50) {
      newErrors.content = '内容至少需要50个字符';
    } else if (data.content.length > 50000) {
      newErrors.content = '内容不能超过50000个字符';
    }

    // 验证分类
    if (!data.category) {
      newErrors.category = '请选择分类';
    }

    // 验证标签
    if (!data.tags || data.tags.length === 0) {
      newErrors.tags = '请至少选择一个标签';
    } else if (data.tags.length > 5) {
      newErrors.tags = '标签数量不能超过5个';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, []);

  /**
   * 提交帖子
   */
  const submitPost = useCallback(async (data: PostFormData): Promise<void> => {
    // 表单验证
    if (!validateForm(data)) {
      message.error('请检查表单填写');
      throw new Error('表单验证失败');
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      // 准备媒体文件数据
      const mediaFiles = data.mediaFiles
        ?.filter(file => file.status === 'done' && file.url)
        .map(file => ({
          url: file.url!,
          type: file.type,
          fileName: file.name,
          fileSize: file.size
        }));

      // 调用API创建帖子
      const response = await communityService.createPost({
        title: data.title.trim(),
        content: data.content.trim(),
        category: data.category,
        tags: data.tags,
        thumbnail: data.thumbnail,
        mediaFiles
      });

      if (response) {
        message.success('发布成功！');
        onSuccess?.(response.id);
      } else {
        throw new Error('发布失败');
      }
    } catch (error) {
      console.error('usePostCreation: submitPost error', error);

      const errorMessage = error instanceof Error ? error.message : '发布失败，请稍后重试';
      message.error(errorMessage);

      // 错误回调
      const errorObj = error instanceof Error ? error : new Error(errorMessage);
      onError?.(errorObj);

      throw errorObj;
    } finally {
      setIsSubmitting(false);
    }
  }, [validateForm, onSuccess, onError]);

  /**
   * 清除错误信息
   */
  const clearErrors = useCallback(() => {
    setErrors({});
  }, []);

  return {
    isSubmitting,
    errors,
    validateForm,
    submitPost,
    clearErrors
  };
}

/**
 * 草稿管理Hook
 *
 * 处理草稿的自动保存和恢复
 */
export interface UseDraftManagerOptions {
  autoSaveInterval?: number; // 自动保存间隔（毫秒）
  draftKey?: string; // 草稿存储的key
}

export interface PostDraft extends PostFormData {
  savedAt: number;
  id?: string;
}

export function useDraftManager(options: UseDraftManagerOptions = {}) {
  const {
    autoSaveInterval = 2000,
    draftKey = 'community_post_draft'
  } = options;

  const [draft, setDraft] = useState<PostDraft | null>(null);

  /**
   * 保存草稿到localStorage
   */
  const saveDraft = useCallback((data: PostFormData) => {
    try {
      const draftData: PostDraft = {
        ...data,
        savedAt: Date.now()
      };

      localStorage.setItem(draftKey, JSON.stringify(draftData));
      setDraft(draftData);

      console.log('Draft saved:', draftData);
    } catch (error) {
      console.error('Failed to save draft:', error);
    }
  }, [draftKey]);

  /**
   * 加载草稿
   */
  const loadDraft = useCallback((): PostDraft | null => {
    try {
      const saved = localStorage.getItem(draftKey);
      if (saved) {
        const draftData = JSON.parse(saved) as PostDraft;
        setDraft(draftData);
        return draftData;
      }
    } catch (error) {
      console.error('Failed to load draft:', error);
    }
    return null;
  }, [draftKey]);

  /**
   * 清除草稿
   */
  const clearDraft = useCallback(() => {
    try {
      localStorage.removeItem(draftKey);
      setDraft(null);
      console.log('Draft cleared');
    } catch (error) {
      console.error('Failed to clear draft:', error);
    }
  }, [draftKey]);

  /**
   * 检查是否有草稿
   */
  const hasDraft = useCallback((): boolean => {
    try {
      const saved = localStorage.getItem(draftKey);
      return !!saved;
    } catch (error) {
      return false;
    }
  }, [draftKey]);

  return {
    draft,
    saveDraft,
    loadDraft,
    clearDraft,
    hasDraft
  };
}
