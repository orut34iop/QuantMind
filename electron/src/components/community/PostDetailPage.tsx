/**
 * 帖子详情页组件
 * Post Detail Page Component
 *
 * 显示帖子的完整内容、作者信息、评论列表等
 *
 * @author QuantMind Team
 * @date 2025-11-19
 */

import React, { useState, useEffect } from 'react';
import { message } from 'antd';
import {
  ArrowLeft,
  Eye,
  MessageCircle,
  Calendar,
  User,
  TrendingUp,
  Share2
} from 'lucide-react';
import type { CommunityPost } from './types';
import { formatNumber, formatTimeAgo } from './communityUtils';
import { PostActions } from './interactions/PostActions';
import { CommentSection } from './comments/CommentSection';
import { communityService } from '../../services/communityService';
import { useAuth } from '../../features/auth/hooks/useAuth';
import './PostDetailPage.css';

interface PostDetailPageProps {
  postId: number;
  onBack: () => void;
}

export const PostDetailPage: React.FC<PostDetailPageProps> = ({ postId, onBack }) => {
  const [post, setPost] = useState<CommunityPost | null>(null);
  const [recommendations, setRecommendations] = useState<Array<{ id: number; title: string; views: number; comments: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFollowing, setIsFollowing] = useState(false);
  const [followLoading, setFollowLoading] = useState(false);
  const [authorFollowers, setAuthorFollowers] = useState<number | null>(null);
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    loadPostDetail();
    loadRecommendations();
  }, [postId]);

  const loadPostDetail = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await communityService.getPostDetail(postId);
      setPost(data as unknown as CommunityPost);
      const followers = Number((data as any)?.authorInfo?.followers_count);
      setAuthorFollowers(Number.isFinite(followers) ? followers : null);
    } catch (err) {
      setError('加载帖子详情失败，请稍后重试');
      console.error('Load post detail error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadRecommendations = async () => {
    try {
      const data = await communityService.getRecommendations(3);
      setRecommendations(data);
    } catch (err) {
      console.error('Load recommendations error:', err);
    }
  };

  const authorId = post?.authorInfo?.id || post?.author || '';

  useEffect(() => {
    if (!authorId) return;
    let canceled = false;
    communityService
      .getAuthorFollowStatus(authorId)
      .then((res) => {
        if (canceled) return;
        setIsFollowing(Boolean(res.isFollowing));
        setAuthorFollowers(res.followers);
      })
      .catch(() => {
        if (canceled) return;
        setIsFollowing(false);
      });
    return () => {
      canceled = true;
    };
  }, [authorId]);

  const handleToggleFollow = async () => {
    if (!authorId) return;
    if (!isAuthenticated) {
      message.warning('请先登录后再关注作者');
      return;
    }
    if (followLoading) return;

    try {
      setFollowLoading(true);
      const res = isFollowing
        ? await communityService.unfollowAuthor(authorId)
        : await communityService.followAuthor(authorId);
      setIsFollowing(Boolean(res.isFollowing));
      setAuthorFollowers(res.followers);
      message.success(res.isFollowing ? '已关注作者' : '已取消关注');
    } catch (err: any) {
      const msg = err?.message || '关注操作失败，请稍后重试';
      message.error(msg);
    } finally {
      setFollowLoading(false);
    }
  };

  // 加载状态
  if (loading) {
    return (
      <div className="w-full h-full bg-[#f1f5f9] flex items-center justify-center">
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl p-16 flex flex-col items-center gap-6 shadow-xl border border-white/50">
          <div className="w-12 h-12 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin" />
          <div className="flex flex-col items-center gap-1">
            <p className="text-sm font-black text-slate-800 uppercase tracking-widest">Loading Content</p>
            <p className="text-xs font-medium text-slate-400">Please wait a moment...</p>
          </div>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error || !post) {
    return (
      <div className="w-full h-full bg-[#f1f5f9] flex items-center justify-center">
        <div className="bg-white rounded-2xl p-12 text-center shadow-sm border border-gray-100">
          <p className="text-slate-800 font-bold mb-6">{error || '该动态已不存在'}</p>
          <button
            className="px-6 py-2 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-colors"
            onClick={onBack}
          >
            返回动态列表
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-[#f1f5f9] p-6 flex flex-col items-center justify-center overflow-hidden">
      <div
        className="bg-white border border-gray-200 shadow-md flex flex-col flex-shrink-0 overflow-hidden"
        style={{
          width: 'min(100%, 1400px)',
          height: 'min(100%, 900px)',
          borderRadius: '16px',
        }}
      >
        {/* 顶部导航栏 */}
        <div className="flex-shrink-0 bg-white/95 backdrop-blur-md border-b border-gray-200 px-6 flex items-center justify-between z-10 rounded-t-[16px]"
          style={{ height: '60px' }}
        >
          <button
            className="flex items-center gap-2 text-slate-500 hover:text-blue-600 font-bold text-sm transition-colors"
            onClick={onBack}
          >
            <ArrowLeft className="w-4 h-4" />
            <span>返回动态列表</span>
          </button>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-400 uppercase tracking-widest font-black mr-2">Quick Actions</span>
            <button className="p-2 hover:bg-slate-50 text-slate-400 rounded-xl transition-colors">
              <Share2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 主内容区 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar bg-gray-50/30">
          <div className="max-w-7xl mx-auto px-6 py-8 flex gap-8">
            {/* 左侧主内容 */}
            <div className="flex-1 min-w-0">
              <article className="bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
                <header className="mb-8">
                  <div className="flex items-center gap-2 mb-4">
                    {post.featured && (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-600 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-amber-100">
                        精选文章
                      </span>
                    )}
                    {post.pinned && (
                      <span className="px-2 py-0.5 bg-rose-50 text-rose-500 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-rose-100">
                        置顶公告
                      </span>
                    )}
                  </div>

                  <h1 className="text-3xl font-black text-slate-800 leading-tight mb-6">{post.title}</h1>

                  {/* 作者和元信息 */}
                  <div className="flex items-center justify-between py-6 border-y border-gray-50">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center overflow-hidden">
                        {post.authorAvatar || post.authorInfo?.avatar ? (
                          <img src={post.authorAvatar || post.authorInfo?.avatar} alt={post.author} className="w-full h-full object-cover" />
                        ) : (
                          <div className="font-black text-slate-400 text-lg uppercase">{post.author.charAt(0)}</div>
                        )}
                      </div>
                      <div>
                        <div className="text-base font-black text-slate-800">{post.author}</div>
                        <div className="text-xs text-slate-400 font-bold uppercase tracking-wider mt-0.5">Strategy Researcher</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6 text-[11px] font-black text-slate-400 uppercase tracking-widest">
                      <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" /> {formatTimeAgo(post.createdAt)}</span>
                      <span className="flex items-center gap-1.5"><Eye className="w-4 h-4" /> {formatNumber(post.views)} Views</span>
                    </div>
                  </div>
                </header>

                {/* 文章内容 */}
                <div
                  className="prose prose-slate max-w-none mb-12 text-slate-600 font-medium leading-loose"
                  dangerouslySetInnerHTML={{ __html: post.content || post.excerpt }}
                />

                {/* 底部标签和互动 */}
                <footer className="pt-8 border-t border-gray-100">
                  <div className="flex items-center gap-2 mb-8 flex-wrap">
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest mr-2">Tags</span>
                    {post.tags?.map((tag) => (
                      <span key={tag} className="px-3 py-1 bg-slate-50 text-slate-500 rounded-xl text-xs font-bold border border-slate-100 hover:bg-blue-50 hover:text-blue-600 transition-colors cursor-pointer">
                        #{tag}
                      </span>
                    ))}
                  </div>

                  <div className="bg-slate-50/50 rounded-2xl p-1 border border-slate-100 inline-block">
                    <PostActions
                      post={post}
                      postId={post.id}
                      postTitle={post.title}
                      likes={post.likes}
                      comments={post.comments}
                      collections={post.collections}
                      isLiked={post.isLiked}
                      isCollected={post.isCollected}
                      showAddStrategyButton={!!post.strategy_metadata}
                    />
                  </div>
                </footer>
              </article>

              {/* 评论区 */}
              <div className="mt-8 bg-white rounded-2xl border border-gray-200 p-8 shadow-sm">
                <div className="flex items-center gap-2 mb-8">
                  <MessageCircle className="w-5 h-5 text-blue-500" />
                  <h2 className="text-base font-black text-slate-800 uppercase tracking-wider">讨论交流 ({post.comments})</h2>
                </div>
                <CommentSection postId={post.id} />
              </div>
            </div>

            {/* 右侧边栏 */}
            <aside className="w-[360px] flex-shrink-0 space-y-6">
              {/* 作者卡片 */}
              <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm flex flex-col items-center text-center">
                <div className="w-20 h-20 rounded-3xl bg-slate-50 border-4 border-white shadow-xl flex items-center justify-center overflow-hidden mb-4">
                  {post.authorAvatar || post.authorInfo?.avatar ? (
                    <img src={post.authorAvatar || post.authorInfo?.avatar} alt={post.author} className="w-full h-full object-cover" />
                  ) : (
                    <div className="font-black text-slate-300 text-3xl uppercase">{post.author.charAt(0)}</div>
                  )}
                </div>
                <div className="text-xl font-black text-slate-800 mb-1">{post.author}</div>
                <p className="text-xs text-slate-400 font-medium leading-relaxed mb-6 px-4">
                  {post.authorInfo?.bio || '量化投资爱好者，专注于技术分析和策略研发。'}
                </p>

                <div className="w-full grid grid-cols-3 gap-2 mb-6 bg-slate-50/50 p-4 rounded-2xl border border-slate-100">
                  <div>
                    <div className="text-base font-black text-slate-800">
                      {formatNumber(post.authorInfo?.posts_count || 0)}
                    </div>
                    <div className="text-[9px] text-gray-400 font-bold uppercase tracking-tighter">Posts</div>
                  </div>
                  <div className="border-x border-slate-200">
                    <div className="text-base font-black text-slate-800">
                      {formatNumber((authorFollowers ?? post.authorInfo?.followers_count) || 0)}
                    </div>
                    <div className="text-[9px] text-gray-400 font-bold uppercase tracking-tighter">Fans</div>
                  </div>
                  <div>
                    <div className="text-base font-black text-slate-800">
                      {formatNumber(post.authorInfo?.likes_received || 0)}
                    </div>
                    <div className="text-[9px] text-gray-400 font-bold uppercase tracking-tighter">Likes</div>
                  </div>
                </div>

                <button
                  onClick={handleToggleFollow}
                  disabled={followLoading}
                  className={`w-full py-3 rounded-xl font-black text-sm shadow-md hover:shadow-lg transition-all active:scale-95 ${
                    isFollowing
                      ? 'bg-slate-100 text-slate-700 border border-slate-200'
                      : 'bg-gradient-to-r from-blue-500 to-purple-600 text-white'
                  } ${followLoading ? 'opacity-60 cursor-not-allowed' : ''}`}
                >
                  {followLoading ? '处理中...' : (isFollowing ? '已关注' : '关注作者')}
                </button>
              </div>

              {/* 热门话题 */}
              <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                  <TrendingUp className="w-4 h-4 text-emerald-500" />
                  <h3 className="text-sm font-black text-gray-800 uppercase tracking-widest">推荐阅读</h3>
                </div>
                <div className="space-y-4">
                  {recommendations.length > 0 ? (
                    recommendations.map((item) => (
                      <div key={item.id} className="group cursor-pointer">
                        <div className="text-sm font-bold text-slate-700 group-hover:text-blue-600 transition-colors mb-2 leading-snug">
                          {item.title}
                        </div>
                        <div className="flex items-center gap-3 text-[10px] font-black text-slate-300 uppercase tracking-tighter">
                          <span className="flex items-center gap-1"><Eye className="w-3 h-3" /> {formatNumber(item.views)}</span>
                          <span className="flex items-center gap-1"><MessageCircle className="w-3 h-3" /> {formatNumber(item.comments)}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-400 font-medium py-4">暂无相关推荐</div>
                  )}
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PostDetailPage;
