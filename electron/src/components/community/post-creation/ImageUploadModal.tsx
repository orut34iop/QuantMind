/**
 * 图片上传模态框组件
 *
 * 提供图片上传、预览、裁剪等功能
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState, useCallback, useRef } from 'react';
import { X, Image as ImageIcon, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { communityMediaUploadService } from '../../../services/communityMediaUploadService';

export interface ImageUploadModalProps {
  visible: boolean;
  onClose: () => void;
  onImageUploaded: (imageUrl: string) => void;
  maxSize?: number; // MB
  maxImages?: number;
}

interface UploadingImage {
  id: string;
  file: File;
  preview: string;
  progress: number;
  status: 'uploading' | 'success' | 'error';
  url?: string;
  error?: string;
}

export const ImageUploadModal: React.FC<ImageUploadModalProps> = ({
  visible,
  onClose,
  onImageUploaded,
  maxSize = 10,
  maxImages = 9,
}) => {
  const [images, setImages] = useState<UploadingImage[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 压缩图片
  const compressImage = useCallback(async (file: File, maxWidth = 1920, maxHeight = 1080, quality = 0.8): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          let { width, height } = img;

          // 计算缩放比例
          if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width *= ratio;
            height *= ratio;
          }

          canvas.width = width;
          canvas.height = height;

          const ctx = canvas.getContext('2d');
          if (!ctx) {
            reject(new Error('无法获取canvas上下文'));
            return;
          }

          ctx.drawImage(img, 0, 0, width, height);

          canvas.toBlob(
            (blob) => {
              if (blob) {
                resolve(blob);
              } else {
                reject(new Error('图片压缩失败'));
              }
            },
            'image/jpeg',
            quality
          );
        };
        img.onerror = () => reject(new Error('图片加载失败'));
        img.src = e.target?.result as string;
      };
      reader.onerror = () => reject(new Error('文件读取失败'));
      reader.readAsDataURL(file);
    });
  }, []);

  // 验证图片文件
  const validateImage = useCallback((file: File): string | null => {
    // 检查文件类型
    if (!file.type.startsWith('image/')) {
      return '只能上传图片文件';
    }

    // 检查文件大小
    if (file.size > maxSize * 1024 * 1024) {
      return `图片大小不能超过 ${maxSize}MB`;
    }

    // 检查图片数量
    if (images.length >= maxImages) {
      return `最多只能上传 ${maxImages} 张图片`;
    }

    return null;
  }, [images, maxSize, maxImages]);

  // 上传单张图片
  const uploadImage = useCallback(async (image: UploadingImage) => {
    try {
      // 更新状态为上传中
      (setImages as any)((prev: UploadingImage[]) => prev.map(img =>
        img.id === image.id ? { ...img, status: 'uploading' as const, progress: 0 } : img
      ));

      // 压缩图片
      const compressedBlob = await compressImage(image.file);
      const compressedFile = new File([compressedBlob], image.file.name, { type: 'image/jpeg' });

      // 上传到后端代理
      const result = await communityMediaUploadService.uploadImage(compressedFile, (progress) => {
        (setImages as any)((prev: UploadingImage[]) => prev.map(img =>
          img.id === image.id ? { ...img, progress: progress.percent } : img
        ));
      });

      if (result.success) {
        // 上传成功
        (setImages as any)((prev: UploadingImage[]) => prev.map(img =>
          img.id === image.id
            ? { ...img, status: 'success' as const, url: result.url, progress: 100 }
            : img
        ));
        onImageUploaded(result.url as string);
      } else {
        throw new Error(result.error || '上传失败');
      }
    } catch (error) {
      console.error('图片上传失败:', error);
      (setImages as any)((prev: UploadingImage[]) => prev.map(img =>
        img.id === image.id
          ? {
            ...img,
            status: 'error' as const,
            error: error instanceof Error ? error.message : '上传失败',
          }
          : img
      ));
    }
  }, [compressImage, onImageUploaded]);

  // 处理文件选择
  const handleFileSelect = useCallback(async (files: File[]) => {
    const validFiles: File[] = [];
    const errors: string[] = [];

    // 验证所有文件
    for (const file of files) {
      const error = validateImage(file);
      if (error) {
        errors.push(`${file.name}: ${error}`);
      } else {
        validFiles.push(file);
      }
    }

    if (errors.length > 0) {
      alert(errors.join('\n'));
    }

    if (validFiles.length === 0) return;

    // 创建预览
    const newImages: UploadingImage[] = await Promise.all(
      validFiles.map(async (file) => {
        const preview = URL.createObjectURL(file);
        return {
          id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          file,
          preview,
          progress: 0,
          status: 'uploading' as const,
        };
      })
    );

    (setImages as any)((prev: UploadingImage[]) => [...prev, ...newImages]);

    // 开始上传
    newImages.forEach(image => uploadImage(image));
  }, [validateImage, uploadImage]);

  // 拖拽处理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    handleFileSelect(files);
  };

  // 文件选择器
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      handleFileSelect(files);
    }
  };

  // 删除图片
  const removeImage = useCallback((id: string) => {
    (setImages as any)((prev: UploadingImage[]) => {
      const image = prev.find(img => img.id === id);
      if (image) {
        URL.revokeObjectURL(image.preview);
      }
      return prev.filter(img => img.id !== id);
    });
  }, []);

  // 重试上传
  const retryUpload = useCallback((id: string) => {
    const image = images.find(img => img.id === id);
    if (image) {
      uploadImage(image);
    }
  }, [images, uploadImage]);

  // 清理
  const cleanup = useCallback(() => {
    images.forEach(img => URL.revokeObjectURL(img.preview));
    setImages([]);
  }, [images]);

  const handleClose = () => {
    cleanup();
    onClose();
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">上传图片</h3>
          <button
            type="button"
            onClick={handleClose}
            aria-label="关闭模态框"
            title="关闭"
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 内容区 */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* 上传区域 */}
          <div
            className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${dragOver
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400 bg-white'
              }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*"
              onChange={handleFileInputChange}
              className="hidden"
            />

            <div className="flex flex-col items-center space-y-3">
              <ImageIcon className="w-12 h-12 text-gray-400" />

              <div className="text-sm text-gray-600">
                拖拽图片到此处，或
                <button
                  type="button"
                  aria-label="选择图片"
                  title="选择图片"
                  className="ml-1 text-blue-600 hover:text-blue-700 underline"
                  onClick={() => fileInputRef.current?.click()}
                >
                  点击选择图片
                </button>
              </div>

              <div className="text-xs text-gray-400">
                支持 JPG、PNG、GIF 格式，单张图片最大 {maxSize}MB，最多 {maxImages} 张
              </div>
            </div>
          </div>

          {/* 图片列表 */}
          {images.length > 0 && (
            <div className="mt-6 grid grid-cols-3 gap-4">
              {images.map((image) => (
                <div
                  key={image.id}
                  className="relative group aspect-square bg-gray-100 rounded-lg overflow-hidden"
                >
                  {/* 图片预览 */}
                  <img
                    src={image.preview}
                    alt="预览"
                    className="w-full h-full object-cover"
                  />

                  {/* 状态覆盖层 */}
                  <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                    {image.status === 'uploading' && (
                      <div className="text-white text-center">
                        <Loader className="w-8 h-8 animate-spin mx-auto mb-2" />
                        <div className="text-sm">{image.progress}%</div>
                      </div>
                    )}

                    {image.status === 'success' && (
                      <CheckCircle className="w-8 h-8 text-green-500" />
                    )}

                    {image.status === 'error' && (
                      <div className="text-white text-center px-4">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 text-red-500" />
                        <div className="text-xs">{image.error}</div>
                        <button
                          type="button"
                          aria-label="重试上传"
                          title="重试上传"
                          onClick={() => retryUpload(image.id)}
                          className="mt-2 px-3 py-1 bg-white text-gray-900 rounded text-xs hover:bg-gray-100"
                        >
                          重试
                        </button>
                      </div>
                    )}
                  </div>

                  {/* 删除按钮 */}
                  <button
                    type="button"
                    onClick={() => removeImage(image.id)}
                    aria-label="删除图片"
                    title="删除图片"
                    className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 底部 */}
        <div className="flex items-center justify-between px-6 py-4 border-t bg-gray-50">
          <div className="text-sm text-gray-600">
            已上传 {images.filter(img => img.status === 'success').length} / {images.length} 张
          </div>
          <div className="flex space-x-3">
            <button
              type="button"
              aria-label="关闭"
              title="关闭"
              onClick={handleClose}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageUploadModal;
