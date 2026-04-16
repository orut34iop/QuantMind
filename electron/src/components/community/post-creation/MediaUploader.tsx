/**
 * 媒体上传组件
 * 支持图片、视频和附件上传
 */

import React, { useState, useRef } from 'react';
import { Upload, Button, Progress, message, Image, Space, Tag, Tooltip } from 'antd';
import {
  PictureOutlined,
  VideoCameraOutlined,
  PaperClipOutlined,
  DeleteOutlined,
  EyeOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { communityMediaUploadService } from '../../../services/communityMediaUploadService';
import type { MediaUploadResult, UploadProgress } from '../../../services/communityMediaUploadService';
import './media-uploader.css';

export interface MediaFile {
  uid: string;
  name: string;
  url?: string;
  status: 'uploading' | 'done' | 'error';
  type: 'image' | 'video' | 'attachment';
  size: number;
  progress?: number;
  error?: string;
  previewUrl?: string;
}

export interface MediaUploaderProps {
  value?: MediaFile[];
  onChange?: (files: MediaFile[]) => void;
  maxImages?: number;
  maxVideos?: number;
  maxAttachments?: number;
  disabled?: boolean;
}

export const MediaUploader: React.FC<MediaUploaderProps> = ({
  value = [],
  onChange,
  maxImages = 9,
  maxVideos = 1,
  maxAttachments = 3,
  disabled = false
}) => {
  const [files, setFiles] = useState<MediaFile[]>(value);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);

  // 更新文件列表
  const updateFiles = (newFiles: MediaFile[]) => {
    setFiles(newFiles);
    onChange?.(newFiles);
  };

  // 统计各类型文件数量
  const getTypeCounts = () => {
    return {
      images: files.filter(f => f.type === 'image').length,
      videos: files.filter(f => f.type === 'video').length,
      attachments: files.filter(f => f.type === 'attachment').length
    };
  };

  // 处理文件选择
  const handleFileSelect = async (
    selectedFiles: FileList | null,
    type: 'image' | 'video' | 'attachment'
  ) => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    const counts = getTypeCounts();
    const maxCount = type === 'image' ? maxImages : type === 'video' ? maxVideos : maxAttachments;
    const currentCount = type === 'image' ? counts.images : type === 'video' ? counts.videos : counts.attachments;

    // 检查数量限制
    if (currentCount >= maxCount) {
      message.warning(`最多只能上传${maxCount}个${getTypeLabel(type)}`);
      return;
    }

    const filesToUpload = Array.from(selectedFiles).slice(0, maxCount - currentCount);

    // 创建临时文件对象
    const newFiles: MediaFile[] = filesToUpload.map(file => ({
      uid: `${Date.now()}_${Math.random()}`,
      name: file.name,
      type,
      size: file.size,
      status: 'uploading' as const,
      progress: 0,
      previewUrl: communityMediaUploadService.getPreviewUrl(file) || undefined
    }));

    updateFiles([...files, ...newFiles]);

    // 上传文件
    for (let i = 0; i < filesToUpload.length; i++) {
      const file = filesToUpload[i];
      const mediaFile = newFiles[i];

      try {
        const uploadMethod =
          type === 'image' ? communityMediaUploadService.uploadImage.bind(communityMediaUploadService) :
            type === 'video' ? communityMediaUploadService.uploadVideo.bind(communityMediaUploadService) :
              communityMediaUploadService.uploadAttachment.bind(communityMediaUploadService);

        const result = await uploadMethod(file, (progress: UploadProgress) => {
          // 更新进度
          (setFiles as any)(prev => prev.map(f =>
            f.uid === mediaFile.uid
              ? { ...f, progress: progress.percent }
              : f
          ));
        });

        if (result.success) {
          // 上传成功
          (setFiles as any)(prev => prev.map(f =>
            f.uid === mediaFile.uid
              ? { ...f, status: 'done' as const, url: result.url, progress: 100 }
              : f
          ));
          message.success(`${file.name} 上传成功`);
        } else {
          // 上传失败
          (setFiles as any)(prev => prev.map(f =>
            f.uid === mediaFile.uid
              ? { ...f, status: 'error' as const, error: result.error }
              : f
          ));
          message.error(result.error || '上传失败');
        }
      } catch (error) {
        console.error('上传出错:', error);
        (setFiles as any)(prev => prev.map(f =>
          f.uid === mediaFile.uid
            ? { ...f, status: 'error' as const, error: '上传出错' }
            : f
        ));
      }
    }
  };

  // 删除文件
  const handleRemove = (uid: string) => {
    const fileToRemove = files.find(f => f.uid === uid);
    if (fileToRemove?.previewUrl) {
      URL.revokeObjectURL(fileToRemove.previewUrl);
    }
    updateFiles(files.filter(f => f.uid !== uid));
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
  };

  // 获取类型标签
  const getTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      image: '图片',
      video: '视频',
      attachment: '附件'
    };
    return labels[type] || type;
  };

  // 获取类型颜色
  const getTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      image: 'blue',
      video: 'purple',
      attachment: 'green'
    };
    return colors[type] || 'default';
  };

  const counts = getTypeCounts();

  return (
    <div className="media-uploader">
      {/* 上传按钮组 */}
      <Space size="middle" className="media-uploader__actions">
        <Tooltip title={`最多${maxImages}张图片`}>
          <Button
            icon={<PictureOutlined />}
            onClick={() => imageInputRef.current?.click()}
            disabled={disabled || counts.images >= maxImages}
          >
            上传图片 ({counts.images}/{maxImages})
          </Button>
        </Tooltip>

        <Tooltip title={`最多${maxVideos}个视频`}>
          <Button
            icon={<VideoCameraOutlined />}
            onClick={() => videoInputRef.current?.click()}
            disabled={disabled || counts.videos >= maxVideos}
          >
            上传视频 ({counts.videos}/{maxVideos})
          </Button>
        </Tooltip>

        <Tooltip title={`最多${maxAttachments}个附件`}>
          <Button
            icon={<PaperClipOutlined />}
            onClick={() => attachmentInputRef.current?.click()}
            disabled={disabled || counts.attachments >= maxAttachments}
          >
            上传附件 ({counts.attachments}/{maxAttachments})
          </Button>
        </Tooltip>
      </Space>

      {/* 隐藏的文件输入 */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => handleFileSelect(e.target.files, 'image')}
      />
      <input
        ref={videoInputRef}
        type="file"
        accept="video/mp4,video/webm,video/ogg,video/quicktime"
        style={{ display: 'none' }}
        onChange={(e) => handleFileSelect(e.target.files, 'video')}
      />
      <input
        ref={attachmentInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.zip,.rar,.txt,.csv"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => handleFileSelect(e.target.files, 'attachment')}
      />

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="media-uploader__list">
          {files.map(file => (
            <div key={file.uid} className={`media-item media-item--${file.status}`}>
              <div className="media-item__content">
                {/* 图片预览 */}
                {file.type === 'image' && file.previewUrl && (
                  <div className="media-item__preview">
                    <Image
                      src={file.previewUrl}
                      alt={file.name}
                      width={80}
                      height={80}
                      style={{ objectFit: 'cover', borderRadius: '4px' }}
                    />
                  </div>
                )}

                {/* 视频预览 */}
                {file.type === 'video' && file.previewUrl && (
                  <div className="media-item__preview">
                    <video
                      src={file.previewUrl}
                      width={80}
                      height={80}
                      style={{ objectFit: 'cover', borderRadius: '4px' }}
                    />
                  </div>
                )}

                {/* 附件图标 */}
                {file.type === 'attachment' && (
                  <div className="media-item__icon">
                    <PaperClipOutlined style={{ fontSize: 24 }} />
                  </div>
                )}

                {/* 文件信息 */}
                <div className="media-item__info">
                  <div className="media-item__name">{file.name}</div>
                  <div className="media-item__meta">
                    <Tag color={getTypeColor(file.type)}>{getTypeLabel(file.type)}</Tag>
                    <span className="media-item__size">{formatFileSize(file.size)}</span>
                  </div>

                  {/* 上传进度 */}
                  {file.status === 'uploading' && (
                    <Progress
                      percent={file.progress || 0}
                      size="small"
                      status="active"
                      showInfo={false}
                    />
                  )}

                  {/* 错误信息 */}
                  {file.status === 'error' && (
                    <div className="media-item__error">{file.error || '上传失败'}</div>
                  )}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="media-item__actions">
                {file.status === 'uploading' && (
                  <LoadingOutlined />
                )}
                {file.status === 'done' && file.url && (
                  <Tooltip title="查看">
                    <Button
                      type="text"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => window.open(file.url)}
                    />
                  </Tooltip>
                )}
                <Tooltip title="删除">
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemove(file.uid)}
                    disabled={disabled}
                  />
                </Tooltip>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 提示信息 */}
      <div className="media-uploader__hint">
        支持jpg/png/gif格式图片（最大10MB），mp4/webm视频（最大500MB），pdf/doc/xls等附件（最大50MB）
      </div>
    </div>
  );
};

export default MediaUploader;
