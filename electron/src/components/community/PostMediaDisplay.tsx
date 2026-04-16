/**
 * 帖子媒体展示组件
 * 支持图片、收益曲线等多种媒体类型
 */

import React from 'react';
import type { PostMedia } from './types';
import './PostMediaDisplay.css';

interface PostMediaDisplayProps {
  media?: PostMedia;
  thumbnail?: string | null;  // 兼容旧字段
  size?: 'small' | 'medium' | 'large';
}

/**
 * 绘制简化的收益曲线
 */
const MiniCurve: React.FC<{ data: number[]; benchmark?: number[] }> = ({ data, benchmark }) => {
  if (!data || data.length === 0) return null;

  const width = 180;
  const height = 120;
  const padding = 10;

  // 计算数据范围
  const allData = benchmark ? [...data, ...benchmark] : data;
  const minVal = Math.min(...allData);
  const maxVal = Math.max(...allData);
  const range = maxVal - minVal || 1;

  // 生成路径
  const createPath = (values: number[], color: string) => {
    const points = values.map((val, idx) => {
      const x = padding + (idx / (values.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
      return `${x},${y}`;
    });
    return (
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    );
  };

  return (
    <svg width={width} height={height} className="mini-curve-svg">
      {/* 背景网格 */}
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#e0e0e0" strokeWidth="1" />
      <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#e0e0e0" strokeWidth="1" />

      {/* 基准线 */}
      {benchmark && createPath(benchmark, '#ccc')}

      {/* 收益曲线 */}
      {createPath(data, data[data.length - 1] >= data[0] ? '#52c41a' : '#ff4d4f')}

      {/* 最后一个点 */}
      <circle
        cx={padding + (width - 2 * padding)}
        cy={height - padding - ((data[data.length - 1] - minVal) / range) * (height - 2 * padding)}
        r="3"
        fill={data[data.length - 1] >= data[0] ? '#52c41a' : '#ff4d4f'}
      />
    </svg>
  );
};

/**
 * 收益曲线卡片
 */
const CurveCard: React.FC<{ data: number[]; benchmark?: number[]; stats?: any }> = ({ data, benchmark, stats }) => {
  const totalReturn = data.length > 0 ? ((data[data.length - 1] - data[0]) / data[0] * 100).toFixed(2) : '0.00';
  const isPositive = parseFloat(totalReturn) >= 0;

  return (
    <div className="curve-card">
      <MiniCurve data={data} benchmark={benchmark} />
      <div className="curve-stats">
        <div className={`curve-return ${isPositive ? 'positive' : 'negative'}`}>
          {isPositive ? '+' : ''}{totalReturn}%
        </div>
        {stats && (
          <div className="curve-metrics">
            {stats.sharpe && <span className="metric">Sharpe: {stats.sharpe.toFixed(2)}</span>}
            {stats.maxDrawdown && <span className="metric">回撤: {stats.maxDrawdown.toFixed(1)}%</span>}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * 图片卡片
 */
const ImageCard: React.FC<{ url: string; alt?: string }> = ({ url, alt }) => {
  return (
    <div className="image-card">
      <img src={url} alt={alt || '帖子配图'} loading="lazy" />
    </div>
  );
};

/**
 * 主组件
 */
export const PostMediaDisplay: React.FC<PostMediaDisplayProps> = ({ media, thumbnail, size = 'small' }) => {
  // 优先使用新的 media 字段
  if (media) {
    switch (media.type) {
      case 'curve':
        if (media.curveData) {
          return (
            <div className={`post-media post-media-${size}`}>
              <CurveCard
                data={media.curveData.returns}
                benchmark={media.curveData.benchmark}
                stats={{
                  sharpe: media.curveData.sharpe,
                  maxDrawdown: media.curveData.maxDrawdown,
                  annualReturn: media.curveData.annualReturn,
                }}
              />
            </div>
          );
        }
        break;

      case 'image':
        if (media.url) {
          return (
            <div className={`post-media post-media-${size}`}>
              <ImageCard url={media.url} alt={media.alt} />
            </div>
          );
        }
        break;

      case 'chart':
        // 预留给未来的图表类型
        break;

      case 'none':
      default:
        return null;
    }
  }

  // 兼容旧的 thumbnail 字段
  if (thumbnail) {
    return (
      <div className={`post-media post-media-${size}`}>
        <ImageCard url={thumbnail} alt="策略插图" />
      </div>
    );
  }

  return null;
};

/**
 * 生成模拟收益曲线数据（用于测试）
 */
export const generateMockCurveData = (length: number = 60, trend: 'up' | 'down' | 'volatile' = 'up'): number[] => {
  const data: number[] = [100];

  for (let i = 1; i < length; i++) {
    const random = (Math.random() - 0.5) * 5;
    let trendValue = 0;

    switch (trend) {
      case 'up':
        trendValue = 0.5;
        break;
      case 'down':
        trendValue = -0.3;
        break;
      case 'volatile':
        trendValue = Math.sin(i / 10) * 2;
        break;
    }

    const newValue = data[i - 1] * (1 + (trendValue + random) / 100);
    data.push(Math.max(newValue, 10)); // 防止负数
  }

  return data;
};
