import React from 'react';
import { useNavigate } from 'react-router-dom';
import './CommunityHub.css';
import { CommunityFilters } from './CommunityFilters';
import { CommunityHeader } from './CommunityHeader';
import { CommunityPagination } from './CommunityPagination';
import { CommunitySidebar } from './CommunitySidebar';
import { CommunityFeed } from './CommunityFeed';
import { communityPosts, hotTopics, hotUsers, promoCard } from './communityMockData';
import type { CommunityPost, CommunityPostWithScore, CommunitySort } from './types';
import { buildPaginationRange } from './communityUtils';
import { useAuth } from '../../features/auth/hooks/useAuth';
import { useCommunityPostsWithFallback } from '../../hooks/community';
import { CommunityFeedSkeleton, CommunityError, CommunityEmpty } from './states';
import { PostCreationModal } from './post-creation';
import { usePostCreation } from '../../hooks/community/usePostCreation';
import { PostDetailPage } from './PostDetailPage';
import { useAppSelector } from '../../store';

const NAV_LINKS = ['研究交流', '策略', '问答', '文档', '课程', '比赛', '实盘'];
const SORT_OPTIONS: CommunitySort[] = ['全部', '最新', '最热', '精华'];
const PER_PAGE = 8;

// 开发模式不再强制 Mock：默认走真实 API；必要时可通过环境变量手动开启 Mock。
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_COMMUNITY === 'true';

export const CommunityHub: React.FC = () => {
  const [activeNav, setActiveNav] = React.useState<string>('研究交流');
  const [activeSort, setActiveSort] = React.useState<CommunitySort>('全部');
  const [searchTerm, setSearchTerm] = React.useState('');
  const [currentPage, setCurrentPage] = React.useState(1);
  const [selectedPost, setSelectedPost] = React.useState<CommunityPost | null>(null);
  const [selectedPostId, setSelectedPostId] = React.useState<number | null>(null); // 用于详情页
  const [postModalVisible, setPostModalVisible] = React.useState(false);
  const { isAuthenticated, user, logout } = useAuth();
  const profileUsername = useAppSelector((state) => state.profile.profile?.username);
  const navigate = useNavigate();
  const displayName = profileUsername || user?.full_name || user?.username || user?.email || null;

  // 发帖功能Hook
  const { submitPost } = usePostCreation({
    onSuccess: () => {
      setPostModalVisible(false);
      refetch(); // 刷新列表
    }
  });

  // 使用带降级的Hook获取数据
  const queryParams = React.useMemo(() => ({
    sort: activeSort,
    search: searchTerm,
    page: currentPage,
    pageSize: PER_PAGE,
  }), [activeSort, searchTerm, currentPage]);

  const {
    posts: apiPosts,
    isLoading,
    error,
    refetch,
    hotUsers: apiHotUsers,
    hotTopics: apiHotTopics,
    promo: apiPromo,
  } = useCommunityPostsWithFallback(
    queryParams,
    React.useMemo(() => ({
      // Mock数据
      posts: communityPosts,
      pagination: {
        current: currentPage,
        pageSize: PER_PAGE,
        total: communityPosts.length,
        totalPages: Math.ceil(communityPosts.length / PER_PAGE),
      },
      hotUsers,
      hotTopics,
      promo: promoCard,
    }), [currentPage]),
    USE_MOCK_DATA // 开发模式下强制使用Mock
  );

  // 使用API返回的数据或处理本地数据
  const scoredPosts = React.useMemo<CommunityPostWithScore[]>(
    () =>
      apiPosts.map(post => ({
        ...post,
        score: Math.round((post.likes || 0) * 2 + (post.comments || 0) * 1.5 + (post.views || 0) / 120),
      })),
    [apiPosts]
  );

  const filteredPosts = React.useMemo(() => {
    let list = [...scoredPosts];

    // 根据导航类型过滤
    if (activeNav !== '研究交流') {
      list = list.filter(item =>
        item.category === activeNav || (item.tags && item.tags.includes(activeNav))
      );
    }

    const sortWithPinned = (comparator?: (a: CommunityPostWithScore, b: CommunityPostWithScore) => number) => {
      list.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        if (comparator) {
          const result = comparator(a, b);
          if (result !== 0) {
            return result;
          }
        }
        return b.score - a.score;
      });
    };

    switch (activeSort) {
      case '最新':
        sortWithPinned((a, b) => b.createdAt - a.createdAt);
        break;
      case '最热':
        sortWithPinned((a, b) => b.views - a.views);
        break;
      case '精华':
        list = list.filter(item => item.featured);
        sortWithPinned((a, b) => b.score - a.score);
        break;
      default:
        sortWithPinned();
        break;
    }

    const q = searchTerm.trim().toLowerCase();
    if (q) {
      list = list.filter(item => {
        const haystack = [item.title, item.excerpt, item.author, ...(item.tags || [])]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        return haystack.includes(q);
      });
    }

    return list;
  }, [activeNav, activeSort, scoredPosts, searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredPosts.length / PER_PAGE));

  React.useEffect(() => {
    setCurrentPage(1);
  }, [activeSort, searchTerm]);

  React.useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  React.useEffect(() => {
    if (!selectedPost) return;
    const stillVisible = filteredPosts.some(item => item.id === selectedPost.id);
    if (!stillVisible) {
      setSelectedPost(null);
    }
  }, [filteredPosts, selectedPost]);

  const paginatedPosts = React.useMemo(() => {
    const start = (currentPage - 1) * PER_PAGE;
    return filteredPosts.slice(start, start + PER_PAGE);
  }, [currentPage, filteredPosts]);

  const handleSelectPost = (post: CommunityPost) => {
    // 跳转到详情页
    setSelectedPostId(post.id);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCloseDetail = () => {
    setSelectedPost(null);
  };

  const handleBackToList = () => {
    setSelectedPostId(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handlePagination = (page: number) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
  };

  const paginationRange = React.useMemo(() => buildPaginationRange(currentPage, totalPages), [currentPage, totalPages]);

  React.useEffect(() => {
    const url = new URL(window.location.href);
    const rawId = url.searchParams.get('communityPostId');
    const id = Number(rawId);
    if (Number.isFinite(id) && id > 0) {
      setSelectedPostId(id);
    }
  }, []);

  React.useEffect(() => {
    const url = new URL(window.location.href);
    if (selectedPostId != null) {
      url.searchParams.set('communityPostId', String(selectedPostId));
    } else {
      url.searchParams.delete('communityPostId');
    }
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
  }, [selectedPostId]);

  // 处理导航切换
  const handleNavChange = (nav: string) => {
    setActiveNav(nav);
    setCurrentPage(1); // 切换导航时重置页码
    setSearchTerm(''); // 清空搜索
  };

  // 打开发帖弹窗
  const handleOpenPostModal = () => {
    if (!isAuthenticated) {
      navigate('/auth/login');
      return;
    }
    setPostModalVisible(true);
  };

  // 如果选中了帖子ID，显示详情页
  if (selectedPostId !== null) {
    return <PostDetailPage postId={selectedPostId} onBack={handleBackToList} />;
  }

  return (
    <div className="w-full h-full p-6 overflow-hidden bg-[#f1f5f9]">
      <div
        className="bg-white border border-gray-200 shadow-sm flex flex-col w-full h-full rounded-[16px] overflow-hidden community-main-container"
      >
        <CommunityHeader
          navLinks={NAV_LINKS}
          activeNav={activeNav}
          isAuthenticated={isAuthenticated}
          userName={displayName}
          onNavChange={handleNavChange}
          onLogin={() => navigate('/auth/login')}
          onRegister={() => navigate('/auth/register')}
          onGoProfile={() => navigate('/user-center')}
          onLogout={() => logout()}
          onCreatePost={handleOpenPostModal}
        />

        <div className="flex-1 overflow-y-auto custom-scrollbar bg-gray-50/30">
          <div className="max-w-[1320px] mx-auto px-6 py-8">
            <div className="page-head mb-6">
              <div className="flex flex-col">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest font-bold mb-1">Community Center</span>
                <h1 className="text-2xl font-bold text-gray-800 tracking-tight">{activeNav}</h1>
              </div>
            </div>

            <div className="banner-container mb-8">
              <div className="banner-wide bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-8 flex items-center justify-between shadow-lg shadow-blue-500/10">
                <div className="space-y-2">
                  <div className="text-2xl font-black text-white tracking-tight">QMData Pro</div>
                  <div className="text-blue-100 font-medium">全市场高频分钟/毫秒线数据，毫秒级响应</div>
                </div>
                <button className="px-6 py-2.5 bg-white text-blue-600 rounded-xl font-bold text-sm shadow-sm hover:shadow-md transition-all active:scale-95" type="button">
                  立即开通
                </button>
              </div>
            </div>

            <CommunityFilters
              options={SORT_OPTIONS}
              activeSort={activeSort}
              searchTerm={searchTerm}
              onSortChange={setActiveSort}
              onSearchChange={setSearchTerm}
            />

            <main className="layout flex gap-8 mt-8" role="main">
              <div className="main-content flex-1 min-w-0">
                {/* 加载状态 */}
                {isLoading && <CommunityFeedSkeleton count={PER_PAGE} />}

                {/* 错误状态 */}
                {!isLoading && error && (
                  <CommunityError
                    error={error}
                    onRetry={refetch}
                    type="api"
                  />
                )}

                {/* 空状态 */}
                {!isLoading && !error && paginatedPosts.length === 0 && (
                  <CommunityEmpty
                    type={searchTerm ? 'no-search-results' : 'no-posts'}
                  />
                )}

                {/* 正常内容 */}
                {!isLoading && !error && paginatedPosts.length > 0 && (
                  <CommunityFeed
                    posts={paginatedPosts}
                    selectedPost={selectedPost}
                    onSelectPost={handleSelectPost}
                    onCloseDetail={handleCloseDetail}
                  />
                )}

                {!isLoading && !error && totalPages > 1 && (
                  <div className="mt-8 flex justify-center pb-8">
                    <CommunityPagination currentPage={currentPage} totalPages={totalPages} pages={paginationRange} onPageChange={handlePagination} />
                  </div>
                )}
              </div>

              <aside className="w-[320px] flex-shrink-0">
                <CommunitySidebar
                  hotUsers={(apiHotUsers && apiHotUsers.length > 0) ? apiHotUsers : hotUsers}
                  hotTopics={(apiHotTopics && apiHotTopics.length > 0) ? apiHotTopics : hotTopics}
                  promo={apiPromo || promoCard}
                />
              </aside>
            </main>
          </div>
        </div>

        {/* 发帖弹窗 */}
        <PostCreationModal
          visible={postModalVisible}
          onCancel={() => setPostModalVisible(false)}
          onSubmit={submitPost}
        />
      </div>
    </div>
  );
};
