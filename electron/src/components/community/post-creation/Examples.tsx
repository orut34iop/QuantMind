/**
 * 富文本编辑器和图片上传功能使用示例
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState } from 'react';
import {
  EnhancedPostEditor,
  ImageUploadModal,
  PostCreationPage,
  PostFormData
} from './index';

/**
 * 示例1: 基础的增强版编辑器使用
 */
export const Example1BasicEditor: React.FC = () => {
  const [content, setContent] = useState('');
  const [error, setError] = useState('');

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-4">基础富文本编辑器</h2>

      <EnhancedPostEditor
        value={content}
        onChange={setContent}
        placeholder="开始输入内容..."
        minLength={50}
        maxLength={10000}
        onError={setError}
        maxImageSize={10}
        maxImages={9}
      />

      {error && (
        <div className="mt-2 text-red-600 text-sm">{error}</div>
      )}

      <div className="mt-4 p-4 bg-gray-100 rounded">
        <h3 className="font-semibold mb-2">内容预览:</h3>
        <div dangerouslySetInnerHTML={{ __html: content }} />
      </div>
    </div>
  );
};

/**
 * 示例2: 独立的图片上传模态框
 */
export const Example2ImageUpload: React.FC = () => {
  const [showModal, setShowModal] = useState(false);
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);

  const handleImageUploaded = (imageUrl: string) => {
    (setUploadedImages as any)(prev => [...prev, imageUrl]);
    console.log('图片上传成功:', imageUrl);
  };

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-4">图片上传模态框</h2>

      <button
        onClick={() => setShowModal(true)}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        打开图片上传
      </button>

      {uploadedImages.length > 0 && (
        <div className="mt-4">
          <h3 className="font-semibold mb-2">已上传图片:</h3>
          <div className="grid grid-cols-3 gap-4">
            {uploadedImages.map((url, index) => (
              <img
                key={index}
                src={url}
                alt={`上传图片 ${index + 1}`}
                className="w-full h-32 object-cover rounded"
              />
            ))}
          </div>
        </div>
      )}

      <ImageUploadModal
        visible={showModal}
        onClose={() => setShowModal(false)}
        onImageUploaded={handleImageUploaded}
        maxSize={10}
        maxImages={9}
      />
    </div>
  );
};

/**
 * 示例3: 完整的帖子创建页面
 */
export const Example3PostCreation: React.FC = () => {
  const [showPage, setShowPage] = useState(false);

  const handleSave = async (data: PostFormData) => {
    console.log('保存帖子数据:', data);

    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000));

    alert('帖子发布成功！');
    setShowPage(false);
  };

  const handleCancel = () => {
    if (confirm('确定要取消吗？未保存的内容将丢失。')) {
      setShowPage(false);
    }
  };

  if (!showPage) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-bold mb-4">完整帖子创建页面</h2>
        <button
          onClick={() => setShowPage(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          创建新帖
        </button>
      </div>
    );
  }

  return (
    <PostCreationPage
      mode="create"
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
};

/**
 * 示例4: 编辑现有帖子
 */
export const Example4PostEditing: React.FC = () => {
  const initialData: PostFormData = {
    title: '我的量化策略分享',
    content: '<h2>策略简介</h2><p>这是一个基于均线交叉的量化策略...</p>',
    tags: ['量化策略', '技术分析', 'Python'],
    category: 'strategy',
  };

  const handleSave = async (data: PostFormData) => {
    console.log('更新帖子数据:', data);
    await new Promise(resolve => setTimeout(resolve, 1000));
    alert('帖子更新成功！');
  };

  const handleCancel = () => {
    if (confirm('确定要取消吗？未保存的修改将丢失。')) {
      console.log('取消编辑');
    }
  };

  return (
    <PostCreationPage
      mode="edit"
      initialData={initialData}
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
};

/**
 * 功能特性说明组件
 */
export const FeatureDocumentation: React.FC = () => {
  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-3xl font-bold">富文本编辑器和图片上传功能文档</h1>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">主要功能</h2>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          <li>富文本编辑：支持标题、粗体、斜体、下划线、删除线等格式</li>
          <li>列表：有序列表、无序列表</li>
          <li>引用块和代码块：支持引用和代码高亮</li>
          <li>链接和图片：插入超链接和图片</li>
          <li>颜色设置：文字颜色和背景色</li>
          <li>对齐方式：左对齐、居中、右对齐</li>
          <li>图片上传：支持点击、拖拽、粘贴上传</li>
          <li>图片压缩：自动压缩图片，优化加载速度</li>
          <li>进度显示：实时显示上传进度</li>
          <li>字数统计：实时统计字数，显示限制</li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">图片上传方式</h2>
        <div className="space-y-3">
          <div className="p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">1. 点击工具栏图片按钮</h3>
            <p className="text-sm text-blue-800">点击编辑器工具栏的图片图标，在弹出的模态框中选择或拖拽图片</p>
          </div>

          <div className="p-4 bg-green-50 rounded-lg">
            <h3 className="font-semibold text-green-900 mb-2">2. 直接拖拽图片到编辑器</h3>
            <p className="text-sm text-green-800">将图片文件直接拖拽到编辑器区域，自动上传并插入</p>
          </div>

          <div className="p-4 bg-purple-50 rounded-lg">
            <h3 className="font-semibold text-purple-900 mb-2">3. 粘贴图片</h3>
            <p className="text-sm text-purple-800">从剪贴板粘贴图片（支持截图、复制的图片等）</p>
          </div>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">技术实现</h2>
        <div className="p-4 bg-gray-50 rounded-lg space-y-2">
          <p className="text-sm text-gray-700">
            <strong>编辑器：</strong> 基于 react-quill (Quill.js)
          </p>
          <p className="text-sm text-gray-700">
            <strong>图片存储：</strong> 腾讯云 COS 对象存储
          </p>
          <p className="text-sm text-gray-700">
            <strong>图片压缩：</strong> Canvas API，自动压缩到合适尺寸
          </p>
          <p className="text-sm text-gray-700">
            <strong>上传方式：</strong> 支持普通上传和分片上传（大文件）
          </p>
          <p className="text-sm text-gray-700">
            <strong>安全性：</strong> 文件类型验证、大小限制、数量限制
          </p>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">配置参数</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border border-gray-300">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-4 py-2 border text-left">参数</th>
                <th className="px-4 py-2 border text-left">类型</th>
                <th className="px-4 py-2 border text-left">默认值</th>
                <th className="px-4 py-2 border text-left">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="px-4 py-2 border">maxLength</td>
                <td className="px-4 py-2 border">number</td>
                <td className="px-4 py-2 border">50000</td>
                <td className="px-4 py-2 border">内容最大字数</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border">minLength</td>
                <td className="px-4 py-2 border">number</td>
                <td className="px-4 py-2 border">50</td>
                <td className="px-4 py-2 border">内容最小字数</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border">maxImageSize</td>
                <td className="px-4 py-2 border">number</td>
                <td className="px-4 py-2 border">10</td>
                <td className="px-4 py-2 border">单张图片最大大小(MB)</td>
              </tr>
              <tr>
                <td className="px-4 py-2 border">maxImages</td>
                <td className="px-4 py-2 border">number</td>
                <td className="px-4 py-2 border">9</td>
                <td className="px-4 py-2 border">最多上传图片数量</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">使用建议</h2>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          <li>图片建议上传前先压缩，提高上传速度</li>
          <li>单张图片建议不超过 5MB，系统会自动压缩</li>
          <li>帖子内容建议在 50-10000 字之间</li>
          <li>标题简洁明了，5-100 字符</li>
          <li>至少选择 1 个标签，最多 5 个</li>
          <li>合理使用富文本格式，提高可读性</li>
        </ul>
      </section>
    </div>
  );
};

// 导出所有示例
export default {
  Example1BasicEditor,
  Example2ImageUpload,
  Example3PostCreation,
  Example4PostEditing,
  FeatureDocumentation,
};
