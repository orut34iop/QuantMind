import React from 'react';
import type { CommunityPost, CommunityPostWithScore } from './types';
import { formatNumber, formatTimeAgo } from './communityUtils';

interface CommunityFeedProps {
  posts: CommunityPostWithScore[];
  selectedPost: CommunityPost | null;
  onSelectPost: (post: CommunityPost) => void;
  onCloseDetail: () => void;
}

import { Pin, Award, MessageSquare, ThumbsUp, Eye, Clock } from 'lucide-react';

export const CommunityFeed: React.FC<CommunityFeedProps> = ({ posts, selectedPost, onSelectPost, onCloseDetail }) => {
  return (
    <>
      <section className="space-y-4" aria-label="动态列表">
        {posts.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center text-slate-400 italic shadow-sm">
            未找到相关内容，试试调整筛选条件。
          </div>
        ) : (
          posts.map(post => (
            <article
              className="bg-white rounded-2xl border border-gray-200 p-5 flex gap-6 transition-all hover:border-blue-200 hover:shadow-md group cursor-pointer"
              key={post.id}
              onClick={() => onSelectPost(post)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {post.pinned && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-rose-50 text-rose-500 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-rose-100">
                        <Pin className="w-3 h-3" /> 置顶
                      </span>
                    )}
                    {post.featured && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 text-amber-600 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-amber-100">
                        <Award className="w-3 h-3" /> 精选
                      </span>
                    )}
                    <h3 className="text-base font-bold text-slate-800 group-hover:text-blue-600 transition-colors leading-snug truncate">
                      {post.title}
                    </h3>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-[11px] font-bold text-slate-400 mb-3">
                  <span className="text-slate-600 font-black">{post.author}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatTimeAgo(post.createdAt)}</span>
                </div>

                <p className="text-sm text-slate-500 line-clamp-2 mb-4 leading-relaxed font-medium">
                  {post.excerpt}
                </p>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 text-[11px] font-black text-slate-400">
                    <span className="flex items-center gap-1.5 hover:text-blue-500 transition-colors">
                      <ThumbsUp className="w-3.5 h-3.5" /> {formatNumber(post.likes)}
                    </span>
                    <span className="flex items-center gap-1.5 hover:text-indigo-500 transition-colors">
                      <MessageSquare className="w-3.5 h-3.5" /> {post.comments}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Eye className="w-3.5 h-3.5" /> {formatNumber(post.views)}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {post.tags?.slice(0, 3).map(tag => (
                      <span className="px-2 py-0.5 bg-slate-50 text-slate-500 rounded-lg text-[10px] font-bold border border-slate-100" key={tag}>
                        #{tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {post.thumbnail && (
                <div className="w-28 h-28 flex-shrink-0 rounded-xl overflow-hidden border border-slate-100 shadow-sm hidden sm:block">
                  <img
                    src={post.thumbnail}
                    alt={post.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                </div>
              )}
            </article>
          ))
        )}
      </section>
    </>
  );
};
