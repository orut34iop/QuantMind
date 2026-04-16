/**
 * 社区媒体上传服务
 * 处理社区发帖时的图片、视频、附件上传到腾讯云COS
 */

import axios from 'axios';
import { SERVICE_ENDPOINTS } from '../config/services';
import { authService } from '../features/auth/services/authService';

export interface MediaUploadResult {
  success: boolean;
  url?: string;
  key?: string;
  size?: number;
  error?: string;
  fileName?: string;
  fileType?: string;
}

export interface UploadProgress {
  percent: number;
  loaded: number;
  total: number;
}

export type MediaType = 'image' | 'video' | 'attachment';

export class CommunityMediaUploadService {
  // 文件大小限制（字节）
  private readonly MAX_FILE_SIZE = {
    image: 10 * 1024 * 1024,      // 10MB
    video: 500 * 1024 * 1024,     // 500MB
    attachment: 50 * 1024 * 1024   // 50MB
  };

  // 支持的文件类型
  private readonly ALLOWED_TYPES = {
    image: ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
    video: ['video/mp4', 'video/webm', 'video/ogg', 'video/quicktime'],
    attachment: [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/zip',
      'application/x-rar-compressed',
      'text/plain',
      'text/csv'
    ]
  };

  /**
   * 上传图片
   */
  async uploadImage(
    file: File,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<MediaUploadResult> {
    return this.uploadMedia(file, 'image', onProgress);
  }

  /**
   * 上传视频
   */
  async uploadVideo(
    file: File,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<MediaUploadResult> {
    return this.uploadMedia(file, 'video', onProgress);
  }

  /**
   * 上传附件
   */
  async uploadAttachment(
    file: File,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<MediaUploadResult> {
    return this.uploadMedia(file, 'attachment', onProgress);
  }

  /**
   * 批量上传图片
   */
  async uploadImages(
    files: File[],
    onProgress?: (index: number, progress: UploadProgress) => void
  ): Promise<MediaUploadResult[]> {
    const results: MediaUploadResult[] = [];

    for (let i = 0; i < files.length; i++) {
      const result = await this.uploadImage(
        files[i],
        onProgress ? (progress) => onProgress(i, progress) : undefined
      );
      results.push(result);
    }

    return results;
  }

  /**
   * 通用媒体上传方法
   */
  private async uploadMedia(
    file: File,
    mediaType: MediaType,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<MediaUploadResult> {
    try {
      // 验证文件
      const validation = this.validateFile(file, mediaType);
      if (!validation.valid) {
        return {
          success: false,
          error: validation.error
        };
      }

      // 生成文件路径
      const filePath = this.generateFilePath(file.name, mediaType);

      // 使用XMLHttpRequest上传以支持进度监控
      const result = await this.uploadToCOS(file, filePath, onProgress);

      return result;
    } catch (error) {
      console.error(`上传${mediaType}失败:`, error);
      return {
        success: false,
        error: error instanceof Error ? error.message : '上传失败'
      };
    }
  }

  /**
   * 上传文件到COS
   */
  private async uploadToCOS(
    file: File,
    filePath: string,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<MediaUploadResult> {
    try {
      const userId = this.getCurrentUserId();
      const token = authService.getAccessToken();
      const category =
        file.type.startsWith('image/')
          ? 'image'
          : file.type.startsWith('video/')
            ? 'video'
            : 'document';

      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('category', category);
      formData.append('description', `community-media:${filePath}`);
      formData.append('tags', 'community,post');

      const response = await axios.post(`${SERVICE_ENDPOINTS.API_GATEWAY}/community/upload/image`, formData, {
        timeout: 120000,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        onUploadProgress: (evt) => {
          if (!onProgress || !evt.total) return;
          const percent = Math.round((evt.loaded / evt.total) * 100);
          onProgress({
            percent: Math.min(100, Math.max(0, percent)),
            loaded: evt.loaded,
            total: evt.total,
          });
        },
      });

      const raw = response.data || {};
      const code = Number(raw.code);
      if (!Number.isNaN(code) && code !== 0 && code !== 200) {
        return { success: false, error: raw.message || `上传失败(code=${code})` };
      }
      const data = raw.data || raw;
      const url = String(data.url || data.file_url || '').trim();
      const key = String(
        data.key || data.file_key || data.file_id || this.extractKeyFromUrl(url) || filePath
      ).trim();

      if (!url) {
        return { success: false, error: '上传失败：后端未返回有效 url' };
      }

      return {
        success: true,
        url,
        key,
        size: Number(data.size || data.file_size || file.size),
        fileName: data.filename || file.name,
        fileType: file.type,
      };
    } catch (error: any) {
      const message =
        error?.response?.data?.message ||
        error?.message ||
        '上传失败';
      return { success: false, error: message };
    }
  }

  private extractKeyFromUrl(url: string): string {
    if (!url) return '';
    try {
      const parsed = new URL(url);
      return parsed.pathname.replace(/^\/+/, '');
    } catch {
      return '';
    }
  }

  /**
   * 验证文件
   */
  private validateFile(file: File, mediaType: MediaType): { valid: boolean; error?: string } {
    // 检查文件大小
    const maxSize = this.MAX_FILE_SIZE[mediaType];
    if (file.size > maxSize) {
      return {
        valid: false,
        error: `文件大小超过限制（最大${this.formatFileSize(maxSize)}）`
      };
    }

    // 检查文件类型
    const allowedTypes = this.ALLOWED_TYPES[mediaType];
    if (!allowedTypes.includes(file.type)) {
      return {
        valid: false,
        error: `不支持的文件类型: ${file.type}`
      };
    }

    return { valid: true };
  }

  /**
   * 生成文件路径
   */
  private generateFilePath(fileName: string, mediaType: MediaType): string {
    const timestamp = Date.now();
    const randomStr = Math.random().toString(36).substring(2, 10);
    const ext = fileName.substring(fileName.lastIndexOf('.'));
    const date = new Date();
    const dateStr = `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;

    return `${mediaType}/${dateStr}/${timestamp}_${randomStr}${ext}`;
  }

  /**
   * 格式化文件大小
   */
  private formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + 'KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + 'MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + 'GB';
  }

  /**
   * 获取文件预览URL（如果支持）
   */
  getPreviewUrl(file: File): string | null {
    if (file.type.startsWith('image/')) {
      return URL.createObjectURL(file);
    }
    if (file.type.startsWith('video/')) {
      return URL.createObjectURL(file);
    }
    return null;
  }

  /**
   * 删除COS上的文件
   */
  async deleteFile(key: string): Promise<boolean> {
    try {
      const token = authService.getAccessToken();
      await axios.delete(`${SERVICE_ENDPOINTS.API_GATEWAY}/files/delete`, {
        timeout: 30000,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        data: {
          file_key: key,
          user_id: this.getCurrentUserId(),
        },
      });
      return true;
    } catch (error) {
      console.error('删除文件失败:', error);
      return false;
    }
  }

  private getCurrentUserId(): string {
    try {
      const userRaw = localStorage.getItem('user');
      if (userRaw) {
        const user = JSON.parse(userRaw);
        const userId = String(user?.user_id || user?.id || '').trim();
        if (userId) return userId;
      }
    } catch {
      // noop
    }
    return 'desktop-user';
  }
}

// 导出单例实例
export const communityMediaUploadService = new CommunityMediaUploadService();

export default CommunityMediaUploadService;
