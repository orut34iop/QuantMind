import React from 'react';
import { Button } from 'antd';
import { EditOutlined } from '@ant-design/icons';

export type CommunityNavType = '研究交流' | '策略' | '问答' | '文档' | '课程' | '比赛' | '实盘';

interface CommunityHeaderProps {
  navLinks: string[];
  activeNav?: string;
  isAuthenticated: boolean;
  userName?: string | null;
  onNavChange?: (nav: string) => void;
  onLogin: () => void;
  onRegister: () => void;
  onGoProfile: () => void;
  onLogout: () => void;
  onCreatePost?: () => void;
}

import { Users, LogOut, UserCircle } from 'lucide-react';

export const CommunityHeader: React.FC<CommunityHeaderProps> = ({
  navLinks,
  activeNav,
  isAuthenticated,
  userName,
  onNavChange,
  onLogin,
  onRegister,
  onGoProfile,
  onLogout,
  onCreatePost,
}) => {

  const handleNavClick = (link: string, event: React.MouseEvent) => {
    event.preventDefault();
    if (onNavChange) {
      onNavChange(link);
    }
  };

  return (
    <header className="flex-shrink-0 bg-white/95 backdrop-blur-md border-b border-gray-200 px-6 flex items-center justify-between z-10 rounded-t-[16px]"
      style={{ height: '60px' }}
    >
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-md">
          <Users className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-800 leading-tight">策略社区</h1>
          <p className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Quant Strategy Community</p>
        </div>
      </div>

      <nav className="hidden xl:flex items-center gap-1 mx-4">
        {navLinks.map((link) => (
          <button
            key={link}
            className={`px-3 py-1.5 rounded-xl text-sm font-bold transition-all ${
              activeNav === link
                ? 'text-blue-600 bg-blue-50'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50'
            }`}
            onClick={(e) => handleNavClick(link, e)}
          >
            {link}
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        {isAuthenticated ? (
          <>
            <div className="hidden md:flex flex-col items-end mr-2">
              <span className="text-xs font-bold text-slate-700">{userName || 'Quant用户'}</span>
              <span className="text-[10px] text-emerald-500 font-bold uppercase">Online</span>
            </div>

            <button
              onClick={onGoProfile}
              className="p-2 hover:bg-slate-100 text-slate-500 rounded-xl transition-colors"
              title="个人中心"
            >
              <UserCircle className="w-5 h-5" />
            </button>

            {onCreatePost && (
              <button
                onClick={onCreatePost}
                className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl shadow-sm hover:shadow-md transition-all text-sm font-bold"
              >
                <EditOutlined />
                <span>发布动态</span>
              </button>
            )}

            <button
              onClick={onLogout}
              className="p-2 hover:bg-rose-50 text-rose-400 rounded-xl transition-colors"
              title="退出登录"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </>
        ) : (
          <>
            <button className="px-4 py-1.5 text-slate-500 font-bold text-sm hover:text-blue-500 transition-colors" type="button" onClick={onLogin}>
              登录
            </button>
            <button className="px-5 py-1.5 bg-slate-900 text-white rounded-xl font-bold text-sm hover:bg-slate-800 transition-all" type="button" onClick={onRegister}>
              加入社区
            </button>
          </>
        )}
      </div>
    </header>
  );
};
