import React from 'react';
import type { HotTopic, HotUser, PromoCardData } from './types';
import { SERVICE_URLS } from '../../config/services';

interface CommunitySidebarProps {
  hotUsers: HotUser[];
  hotTopics: HotTopic[];
  promo?: PromoCardData | null;
}

import { Flame, TrendingUp, Users } from 'lucide-react';

export const CommunitySidebar: React.FC<CommunitySidebarProps> = ({ hotUsers, hotTopics, promo }) => {
  const [failedAvatarUrls, setFailedAvatarUrls] = React.useState<Set<string>>(new Set());

  const resolveAvatarUrl = React.useCallback((raw?: string): string => {
    const value = String(raw || '').trim();
    if (!value) return '';
    if (/^(https?:)?\/\//i.test(value) || value.startsWith('data:') || value.startsWith('blob:')) {
      return value;
    }
    const base = String(SERVICE_URLS.API_GATEWAY || '').replace(/\/+$/, '');
    const path = value.startsWith('/') ? value : `/${value}`;
    return `${base}${path}`;
  }, []);

  const markAvatarFailed = React.useCallback((url: string) => {
    if (failedAvatarUrls.has(url)) return;
    const next = new Set(failedAvatarUrls);
    next.add(url);
    setFailedAvatarUrls(next);
  }, [failedAvatarUrls]);

  return (
    <div className="space-y-6">
      {/* 推广卡片 */}
      {promo ? (
        <div className="bg-gradient-to-br from-indigo-600 to-purple-700 rounded-2xl p-6 shadow-lg shadow-indigo-500/20 relative overflow-hidden group">
          <div className="absolute -right-4 -top-4 w-24 h-24 bg-white/10 rounded-full blur-2xl group-hover:bg-white/20 transition-all" />
          <div className="relative z-10">
            <h3 className="text-lg font-black text-white mb-2 leading-tight">{promo.title}</h3>
            <p className="text-xs text-indigo-100 font-medium mb-4 leading-relaxed opacity-90">{promo.description}</p>
            <button className="w-full py-2.5 bg-white text-indigo-600 rounded-xl font-bold text-sm shadow-sm hover:shadow-md transition-all active:scale-95" type="button">
              {promo.actionLabel}
            </button>
          </div>
        </div>
      ) : null}

      {/* 热门用户 */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
        <div className="flex items-center gap-2 mb-4">
          <Users className="w-4 h-4 text-blue-500" />
          <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wider">活跃达人</h2>
        </div>
        <div className="space-y-4">
          {hotUsers.map(user => (
            <div className="flex items-center gap-3 p-1 hover:bg-slate-50 rounded-xl transition-colors cursor-pointer group" key={`${user.id || user.name}-${user.score}`}>
              <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center font-bold text-slate-400 group-hover:bg-blue-50 group-hover:text-blue-500 transition-all overflow-hidden">
                {(() => {
                  const avatarUrl = resolveAvatarUrl(user.avatar);
                  if (!avatarUrl || failedAvatarUrls.has(avatarUrl)) {
                    return user.name.charAt(0);
                  }
                  return (
                    <img
                      src={avatarUrl}
                      alt={user.name}
                      className="w-full h-full object-cover"
                      loading="lazy"
                      referrerPolicy="no-referrer"
                      onError={() => markAvatarFailed(avatarUrl)}
                    />
                  );
                })()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-700 truncate">{user.name}</div>
                <div className="text-[10px] text-gray-400 font-medium flex items-center gap-1.5">
                  影响力
                  <span className={`font-bold ${user.trend === 'up' ? 'text-emerald-500' : 'text-rose-500'}`}>
                    {user.trend === 'up' ? '↑' : '↓'} {user.score}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 热门话题 */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
        <div className="flex items-center gap-2 mb-4">
          <Flame className="w-4 h-4 text-orange-500" />
          <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wider">热门话题</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {hotTopics.map(topic => (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-100 rounded-xl hover:bg-white hover:border-blue-200 hover:shadow-sm transition-all cursor-pointer group" key={topic.name}>
              <span className="text-xs font-bold text-slate-600 group-hover:text-blue-600">#{topic.name}</span>
              <span className="text-[10px] font-black text-slate-300 group-hover:text-blue-300">{topic.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
