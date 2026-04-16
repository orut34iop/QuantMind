import React, { useCallback, useEffect, useMemo } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import CharacterCount from '@tiptap/extension-character-count';
import './post-editor.css';

export interface PostEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  minLength?: number;
  onError?: (error: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * 富文本编辑器组件
 */
export const PostEditor: React.FC<PostEditorProps> = ({
  value,
  onChange,
  placeholder = '请输入内容...',
  maxLength = 50000,
  minLength = 50,
  onError,
  disabled = false,
  className = '',
}) => {
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
      Link.configure({
        openOnClick: false,
        autolink: true,
        protocols: ['http', 'https'],
      }),
      Placeholder.configure({
        placeholder,
      }),
      CharacterCount.configure({
        limit: maxLength,
      }),
    ],
    content: value,
    editable: !disabled,
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const length = editor.storage.characterCount.characters();
      if (maxLength && length > maxLength) {
        onError?.(`内容不能超过 ${maxLength} 字`);
        // 回退到最大长度
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
  }, [value, editor]);

  const currentLength = useMemo(() => {
    return editor?.storage.characterCount.characters() ?? getTextContent(value).length;
  }, [editor, value, getTextContent]);

  // 字数统计样式类
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

  return (
    <div className={`post-editor ${className}`}>
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
        <button onClick={() => editor?.chain().focus().unsetAllMarks().clearNodes().run()}>Clear</button>
      </div>

      <div className={`post-editor__content ${disabled ? 'disabled' : ''}`}>
        <EditorContent editor={editor} />
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

        {currentLength < minLength && (
          <div className="post-editor__hint">
            还需输入至少 {minLength - currentLength} 字
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * 纯文本编辑器（简化版，用于评论等场景）
 */
export interface SimpleEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  disabled?: boolean;
  rows?: number;
}

export const SimpleEditor: React.FC<SimpleEditorProps> = ({
  value,
  onChange,
  placeholder = '请输入内容...',
  maxLength = 1000,
  disabled = false,
  rows = 4,
}) => {
  const currentLength = value.length;

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      if (maxLength && newValue.length > maxLength) {
        return;
      }
      onChange(newValue);
    },
    [onChange, maxLength]
  );

  return (
    <div className="simple-editor">
      <textarea
        value={value}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        className="simple-editor__textarea"
      />
      <div className="simple-editor__footer">
        <span className="simple-editor__counter">
          {currentLength}
          {maxLength && ` / ${maxLength}`}
        </span>
      </div>
    </div>
  );
};

export default PostEditor;
