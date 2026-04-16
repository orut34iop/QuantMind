import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import CharacterCount from '@tiptap/extension-character-count';
import Image from '@tiptap/extension-image';
import './post-editor.css';
import { ImageUploadModal } from './ImageUploadModal';
import { communityMediaUploadService } from '../../../services/communityMediaUploadService';
import { Image as ImageIcon } from 'lucide-react';

export interface EnhancedPostEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  minLength?: number;
  onError?: (error: string) => void;
  disabled?: boolean;
  className?: string;
  // 图片上传相关
  maxImageSize?: number; // MB
  maxImages?: number;
}

/**
 * 增强版富文本编辑器
 */
export const EnhancedPostEditor: React.FC<EnhancedPostEditorProps> = ({
  value,
  onChange,
  placeholder = '请输入内容...',
  maxLength = 50000,
  minLength = 50,
  onError,
  disabled = false,
  className = '',
  maxImageSize = 10,
  maxImages = 9,
}) => {
  const [showImageModal, setShowImageModal] = useState(false);
  const [uploadingImages, setUploadingImages] = useState<Set<string>>(new Set());

  const getTextContent = useCallback((html: string): string => {
    const temp = document.createElement('div');
    temp.innerHTML = html;
    return temp.textContent || temp.innerText || '';
  }, []);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      Link.configure({ openOnClick: false, autolink: true, protocols: ['http', 'https'] }),
      Placeholder.configure({ placeholder }),
      CharacterCount.configure({ limit: maxLength }),
      Image.configure({ inline: false, allowBase64: true }),
    ],
    content: value,
    editable: !disabled,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const length = editor.storage.characterCount.characters();
      if (maxLength && length > maxLength) {
        onError?.(`内容不能超过 ${maxLength} 字`);
        editor.commands.setContent(editor.getHTML().slice(0, -1));
        return;
      }
      onChange(html);
    },
  });

  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value);
    }
  }, [editor, value]);

  const currentLength = useMemo(
    () => editor?.storage.characterCount.characters() ?? getTextContent(value).length,
    [editor, value, getTextContent]
  );

  const toggleLink = useCallback(() => {
    if (!editor) return;
    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('请输入链接地址', previousUrl);
    if (url === null) return;
    if (url === '') {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().setLink({ href: url }).run();
  }, [editor]);

  const insertImage = useCallback(
    async (file: File) => {
      if (!editor) return;
      if (file.size > maxImageSize * 1024 * 1024) {
        onError?.(`图片大小不能超过 ${maxImageSize}MB`);
        return;
      }
      const imageId = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
      (setUploadingImages as any)(prev => new Set(prev).add(imageId));
      try {
        const compressed = await compressImage(file);
        // Convert Blob back to File for the service which expects File
        const compressedFile = new File([compressed], file.name, { type: 'image/jpeg' });

        const result = await communityMediaUploadService.uploadImage(compressedFile);
        if (!result.success) {
          throw new Error(result.error || '上传失败');
        }
        editor.chain().focus().setImage({ src: result.url as string }).run();
      } catch (err) {
        console.error('图片上传失败', err);
        onError?.(err instanceof Error ? err.message : '图片上传失败');
      } finally {
        (setUploadingImages as any)(prev => {
          const next = new Set(prev);
          next.delete(imageId);
          return next;
        });
      }
    },
    [editor, maxImageSize, onError]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
      if (files.length > 0) {
        files.forEach(f => insertImage(f));
      }
    },
    [insertImage]
  );

  const compressImage = (file: File, maxWidth = 1920, maxHeight = 1080, quality = 0.8): Promise<Blob> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => {
        const img = new (window as any).Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          let { width, height } = img;
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
            blob => {
              if (blob) resolve(blob);
              else reject(new Error('图片压缩失败'));
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

  const getCounterClassName = () => {
    const baseClass = 'post-editor__counter';
    if (currentLength < minLength) {
      return `${baseClass} post-editor__counter--warning`;
    }
    if (maxLength && currentLength > maxLength * 0.9) {
      return `${baseClass} post-editor__counter--danger`;
    }
    return baseClass;
  };

  const handleImageUploaded = useCallback(
    (url: string) => {
      editor?.chain().focus().setImage({ src: url }).run();
    },
    [editor]
  );

  return (
    <>
      <div className={`post-editor ${className}`}>
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          <div className="post-editor__toolbar">
            <button onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} className={editor?.isActive('heading', { level: 1 }) ? 'active' : ''}>H1</button>
            <button onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} className={editor?.isActive('heading', { level: 2 }) ? 'active' : ''}>H2</button>
            <button onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()} className={editor?.isActive('heading', { level: 3 }) ? 'active' : ''}>H3</button>
            <span className="divider" />
            <button onClick={() => editor?.chain().focus().toggleBold().run()} className={editor?.isActive('bold') ? 'active' : ''}>B</button>
            <button onClick={() => editor?.chain().focus().toggleItalic().run()} className={editor?.isActive('italic') ? 'active' : ''}>I</button>
            <button onClick={() => editor?.chain().focus().toggleUnderline().run()} className={editor?.isActive('underline') ? 'active' : ''}>U</button>
            <button onClick={() => editor?.chain().focus().toggleStrike().run()} className={editor?.isActive('strike') ? 'active' : ''}>S</button>
            <span className="divider" />
            <button onClick={() => editor?.chain().focus().toggleBulletList().run()} className={editor?.isActive('bulletList') ? 'active' : ''}>• List</button>
            <button onClick={() => editor?.chain().focus().toggleOrderedList().run()} className={editor?.isActive('orderedList') ? 'active' : ''}>1. List</button>
            <button onClick={() => editor?.chain().focus().toggleBlockquote().run()} className={editor?.isActive('blockquote') ? 'active' : ''}>❝</button>
            <button onClick={() => editor?.chain().focus().toggleCodeBlock().run()} className={editor?.isActive('codeBlock') ? 'active' : ''}>{'<>'}</button>
            <span className="divider" />
            <button onClick={toggleLink} className={editor?.isActive('link') ? 'active' : ''}>Link</button>
            <button onClick={() => setShowImageModal(true)} className="flex items-center space-x-1">
              <ImageIcon className="w-4 h-4" />
              <span>图片</span>
            </button>
            <button onClick={() => editor?.chain().focus().unsetAllMarks().clearNodes().run()}>Clear</button>
          </div>

          <div className={`post-editor__content ${disabled ? 'disabled' : ''}`}>
            <EditorContent editor={editor} />
          </div>
        </div>

        <div className="post-editor__footer">
          <div className={getCounterClassName()}>
            <span className="post-editor__counter-current">{currentLength}</span>
            {maxLength && (
              <>
                <span className="post-editor__counter-separator"> / </span>
                <span className="post-editor__counter-max">{maxLength}</span>
              </>
            )}
            <span className="post-editor__counter-unit"> 字</span>
          </div>

          <div className="flex items-center space-x-2 text-xs text-gray-500">
            {uploadingImages.size > 0 && (
              <span className="text-blue-600">
                正在上传 {uploadingImages.size} 张图片...
              </span>
            )}

            {currentLength < minLength && (
              <div className="post-editor__hint">
                还需输入至少 {minLength - currentLength} 字
              </div>
            )}
          </div>
        </div>

        {/* 提示信息 */}
        <div className="mt-2 px-2 text-xs text-gray-500">
          <div className="flex items-center space-x-4">
            <span className="flex items-center">
              <ImageIcon className="w-3 h-3 mr-1" />
              支持拖拽、粘贴和点击工具栏上传图片
            </span>
            <span>单张图片最大 {maxImageSize}MB</span>
            <span>最多 {maxImages} 张图片</span>
          </div>
        </div>
      </div>

      {/* 图片上传模态框 */}
      <ImageUploadModal
        visible={showImageModal}
        onClose={() => setShowImageModal(false)}
        onImageUploaded={handleImageUploaded}
        maxSize={maxImageSize}
        maxImages={maxImages}
      />
    </>
  );
};

export default EnhancedPostEditor;
