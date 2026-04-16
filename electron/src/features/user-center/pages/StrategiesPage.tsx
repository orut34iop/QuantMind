/**
 * 策略管理页面
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStrategies, useDeleteStrategy } from '../hooks';
import { Table, Button, Tag, Space, Popconfirm, message, Input, Select, Modal } from 'antd';
import {
  StarOutlined,
  StarFilled,
} from '@ant-design/icons';
import type { StrategyStatus } from '../types';
import { communityService } from '../../../services/communityService';
import { TagSelector } from '../../../components/common/TagSelector';
import { filterValidTags } from '../../../shared/types/strategyTags';

const { Search } = Input;
const { TextArea } = Input;

interface StrategiesPageProps {
  userId: string;
}

import { Plus, ArrowLeftRight as SwapOutlined, Search as SearchIcon, Share2, Eye, Trash2, RefreshCw, Edit, AlertTriangle } from 'lucide-react';

const StrategiesPage: React.FC<StrategiesPageProps> = ({ userId }) => {
  const navigate = useNavigate();
  const [shareModalVisible, setShareModalVisible] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null);
  const [shareNote, setShareNote] = useState('');
  const [shareTags, setShareTags] = useState<string[]>([]);  // 新增：分享标签
  const [isSharing, setIsSharing] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [strategyToDelete, setStrategyToDelete] = useState<any>(null);

  const {
    strategies,
    total,
    page,
    pageSize,
    isLoading,
    filters,
    handlePageChange,
    handleFilterChange,
    refetch,
  } = useStrategies(userId);

  const { deleteStrategy, deleteStatus } = useDeleteStrategy(userId);

  const handleDeleteClick = (strategy: any) => {
    setStrategyToDelete(strategy);
    setDeleteModalVisible(true);
  };

  const handleConfirmDelete = async () => {
    if (!strategyToDelete) return;

    try {
      await deleteStrategy(strategyToDelete.id);
      message.success('策略已删除');
      refetch();
    } catch (err: any) {
      message.error(err.message || '删除失败');
    } finally {
      setDeleteModalVisible(false);
      setStrategyToDelete(null);
    }
  };

  const handleEdit = (strategy: any) => {
    if (strategy.status === 'repository') {
      Modal.confirm({
        title: '编辑仓库策略',
        icon: <AlertTriangle className="w-5 h-5 text-orange-500" />,
        content: (
          <div className="space-y-2">
            <p>编辑仓库策略将自动降级到草稿状态，需要重新回测验证才能再次晋升到仓库。</p>
            <div className="bg-orange-50 p-3 rounded-lg text-sm">
              <p className="font-semibold text-orange-800">注意事项：</p>
              <ul className="list-disc list-inside text-orange-700 mt-1 space-y-1">
                <li>策略状态将变为"草稿"</li>
                <li>需要重新进行回测验证</li>
                <li>原回测记录将保留作为历史参考</li>
              </ul>
            </div>
          </div>
        ),
        okText: '确认编辑',
        cancelText: '取消',
        onOk: () => {
          message.success(`策略已降级到草稿，正在跳转到 AI-IDE...`);
          // TODO: 调用降级 API
          // 跳转到 AI-IDE 并传递策略 ID
          navigate(`/ai-ide?strategyId=${strategy.id}`);
        },
      });
    } else if (strategy.status === 'live_trading') {
      message.warning('实盘策略无法编辑，请先停止实盘');
    } else {
      // 草稿策略直接跳转到 AI-IDE
      navigate(`/ai-ide?strategyId=${strategy.id}`);
    }
  };

  const handleViewDetail = (strategyId: string) => {
    navigate(`/user-center/strategy/${strategyId}`);
  };

  // 打开分享对话框
  const handleOpenShareModal = (strategy: any) => {
    setSelectedStrategy(strategy);
    const strategyName = strategy.name || strategy.strategy_name || '未命名策略';
    setShareNote(`我的策略"${strategyName}"在${new Date().getFullYear()}年表现优异，年化收益率${strategy.performance_summary?.total_return_pct?.toFixed(2)}%，夏普比率${strategy.performance_summary?.sharpe_ratio?.toFixed(2)}，欢迎大家交流讨论！`);

    // 初始化标签：策略自带标签 + 策略类型
    const initialTags = [
      ...filterValidTags(strategy.tags || []),
      strategy.strategy_type,
    ].filter((tag, index, self) => self.indexOf(tag) === index); // 去重
    setShareTags(initialTags);

    setShareModalVisible(true);
  };

  // 执行分享到社区
  const handleShareToCommunity = async () => {
    if (!selectedStrategy) return;

    setIsSharing(true);
    try {
      // 验证标签
      const validTags = filterValidTags(shareTags);
      if (validTags.length === 0) {
        message.warning('请至少选择一个标签');
        setIsSharing(false);
        return;
      }

      // 构建帖子内容
      const postData = {
        title: `[策略分享] ${selectedStrategy.name || selectedStrategy.strategy_name}`,
        content: shareNote,
        category: '策略',
        tags: validTags,  // 使用统一标签系统
        media: {
          type: 'curve' as const,
          curveData: {
            dates: [], // 实际应用中需要从回测结果获取
            returns: [],
            sharpe: selectedStrategy.performance_summary?.sharpe_ratio,
            maxDrawdown: selectedStrategy.performance_summary?.max_drawdown,
            annualReturn: selectedStrategy.performance_summary?.total_return_pct,
          }
        },
        strategy_metadata: {
          strategy_id: selectedStrategy.id,
          strategy_name: selectedStrategy.name || selectedStrategy.strategy_name,
          strategy_type: selectedStrategy.strategy_type,
          performance_summary: selectedStrategy.performance_summary,
          source_user_id: userId,
        }
      };

      const response = await communityService.createPost(postData);

      const resAny = response as any;
      if (resAny.success) {
        message.success('已成功分享到社区！');
        setShareModalVisible(false);
        setSelectedStrategy(null);
        setShareNote('');
        setShareTags([]);
        refetch(); // 刷新列表，更新分享状态
      } else {
        throw new Error(resAny.message || '分享失败');
      }
    } catch (err: any) {
      console.error('分享到社区失败:', err);
      message.error(err.message || '分享失败，请稍后重试');
    } finally {
      setIsSharing(false);
    }
  };

  const getStatusTag = (status: StrategyStatus) => {
    const statusMap: Record<StrategyStatus, { bg: string; text: string; color: string }> = {
      draft: { bg: 'bg-gray-50', color: 'text-gray-500', text: '草稿' },
      repository: { bg: 'bg-blue-50', color: 'text-blue-600', text: '仓库' },
      live_trading: { bg: 'bg-green-50', color: 'text-green-600', text: '实盘中' },
      active: { bg: 'bg-emerald-50', color: 'text-emerald-600', text: '已激活' },
      inactive: { bg: 'bg-slate-50', color: 'text-slate-400', text: '未激活' },
      paused: { bg: 'bg-amber-50', color: 'text-amber-600', text: '已暂停' },
      archived: { bg: 'bg-rose-50', color: 'text-rose-400', text: '已归档' },
      backtesting: { bg: 'bg-blue-50', color: 'text-blue-600', text: '回测中' },
    };
    const config = statusMap[status] || { bg: 'bg-slate-50', color: 'text-slate-400', text: status };
    return (
      <span className={`px-2 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-tighter border border-transparent ${config.bg} ${config.color}`}>
        {config.text}
      </span>
    );
  };

  const columns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
      width: 240,
      render: (text: string, record: any) => (
        <div className="flex items-center gap-2">
          {record.is_favorite ? (
            <StarFilled className="text-amber-400 text-xs" />
          ) : (
            <StarOutlined className="text-slate-200 text-xs" />
          )}
          <span className="font-bold text-slate-700">{text}</span>
        </div>
      ),
    },
    {
      title: '策略类型',
      dataIndex: 'strategy_type',
      key: 'strategy_type',
      width: 120,
      render: (text: string) => <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{text}</span>
    },
    {
      title: '当前状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: getStatusTag,
    },
    {
      title: '总收益率',
      dataIndex: ['performance_summary', 'total_return_pct'],
      key: 'return',
      width: 120,
      render: (value: number) => (
        <span className={`text-sm font-black font-mono ${value >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
          {value >= 0 ? '+' : ''}{value?.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '夏普比率',
      dataIndex: ['performance_summary', 'sharpe_ratio'],
      key: 'sharpe',
      width: 100,
      render: (value: number) => <span className="text-sm font-bold text-slate-600 font-mono">{value?.toFixed(2) || '-'}</span>,
    },
    {
      title: '回撤',
      dataIndex: ['performance_summary', 'max_drawdown'],
      key: 'drawdown',
      width: 100,
      render: (value: number) => (
        <span className="text-sm font-bold text-rose-400 font-mono">-{Math.abs(value || 0).toFixed(2)}%</span>
      ),
    },
    {
      title: '胜率',
      dataIndex: ['performance_summary', 'win_rate'],
      key: 'winrate',
      width: 100,
      render: (value: number) => <span className="text-sm font-bold text-slate-500 font-mono">{value?.toFixed(2)}%</span>,
    },
    {
      title: '创建于',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (text: string) => <span className="text-[11px] font-black text-slate-300 uppercase tracking-tighter">{new Date(text).toLocaleDateString()}</span>,
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right' as const,
      render: (_: any, record: any) => (
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleViewDetail(record.strategy_id)}
            className="p-2 hover:bg-blue-50 text-slate-400 hover:text-blue-500 rounded-xl transition-colors"
            title="查看详情"
          >
            <Eye size={16} />
          </button>
          {record.status !== 'live_trading' && (
            <button
              onClick={() => handleEdit(record)}
              className={`p-2 rounded-xl transition-colors ${record.status === 'repository'
                ? 'hover:bg-orange-50 text-slate-400 hover:text-orange-500'
                : 'hover:bg-purple-50 text-slate-400 hover:text-purple-500'
                }`}
              title={record.status === 'repository' ? '编辑（将降级到草稿）' : '编辑策略'}
            >
              <Edit size={16} />
            </button>
          )}
          <button
            onClick={() => handleOpenShareModal(record)}
            disabled={record.is_shared}
            className={`p-2 rounded-xl transition-colors ${record.is_shared ? 'text-slate-200 cursor-not-allowed' : 'hover:bg-indigo-50 text-slate-400 hover:text-indigo-500'}`}
            title={record.is_shared ? '已分享到社区' : '分享到社区'}
          >
            <Share2 size={16} />
          </button>
          {record.status !== 'live_trading' && (
            <button
              onClick={() => handleDeleteClick(record)}
              className="p-2 hover:bg-rose-50 text-slate-400 hover:text-rose-500 rounded-xl transition-colors"
              title="删除策略"
            >
              {deleteStatus === 'loading' ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Trash2 size={16} />}
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="strategies-page">
      {/* 筛选器 */}
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="relative">
            <SearchIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              placeholder="搜索策略..."
              className="pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm font-medium focus:ring-4 focus:ring-blue-500/10 outline-none transition-all w-64 shadow-sm"
              onChange={(e) => handleFilterChange({ search: e.target.value })}
            />
          </div>
          <Select
            placeholder="所有状态"
            className="w-36 h-10 rounded-xl custom-select-xl shadow-sm"
            bordered={true}
            allowClear
            value={filters.status}
            onChange={(status: StrategyStatus) => handleFilterChange({ status })}
          >
            <Select.Option value="draft">草稿</Select.Option>
            <Select.Option value="repository">仓库</Select.Option>
            <Select.Option value="live_trading">实盘中</Select.Option>
            <Select.Option value="active">已激活</Select.Option>
            <Select.Option value="inactive">未激活</Select.Option>
            <Select.Option value="paused">已暂停</Select.Option>
            <Select.Option value="archived">已归档</Select.Option>
            <Select.Option value="backtesting">回测中</Select.Option>
          </Select>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/strategy-comparison')}
            className="flex items-center gap-2 px-4 py-2 bg-slate-50 text-slate-600 border border-slate-200 rounded-xl font-bold text-sm hover:bg-slate-100 transition-all"
          >
            <SwapOutlined className="text-xs" />
            <span>策略对比</span>
          </button>
          <button className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-black text-sm shadow-md hover:shadow-lg transition-all active:scale-95">
            <Plus className="w-4 h-4" />
            <span>创建新策略</span>
          </button>
        </div>
      </div>

      {/* 策略列表 */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <Table
          columns={columns}
          dataSource={strategies}
          rowKey="id"
          loading={isLoading}
          scroll={{ x: 1200 }}
          className="custom-modern-table"
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: handlePageChange,
            showSizeChanger: false,
            showTotal: (total) => <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Total {total} Strategy Records</span>,
          }}
        />
      </div>

      {/* 分享到社区对话框 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <Share2 className="w-5 h-5 text-indigo-500" />
            <span className="font-black text-slate-800">分享策略到社区</span>
          </div>
        }
        open={shareModalVisible}
        onOk={handleShareToCommunity}
        onCancel={() => {
          setShareModalVisible(false);
          setSelectedStrategy(null);
          setShareNote('');
        }}
        confirmLoading={isSharing}
        width={640}
        okText="确认发布动态"
        cancelText="取消"
        className="custom-modern-modal"
        okButtonProps={{ className: 'rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 border-none font-bold' }}
        cancelButtonProps={{ className: 'rounded-xl font-bold' }}
      >
        <div className="py-4 space-y-6">
          <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100">
            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Strategy Preview</div>
            <div className="flex items-center justify-between mb-6">
              <div className="text-xl font-black text-slate-800">{selectedStrategy?.name || selectedStrategy?.strategy_name}</div>
              <div className="text-xs font-bold text-slate-400">{selectedStrategy?.strategy_type}</div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className={`text-lg font-black ${selectedStrategy?.performance_summary?.total_return_pct >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                  {selectedStrategy?.performance_summary?.total_return_pct?.toFixed(2)}%
                </div>
                <div className="text-[9px] text-gray-400 font-bold uppercase">Return</div>
              </div>
              <div className="text-center border-x border-slate-200">
                <div className="text-lg font-black text-slate-700">{selectedStrategy?.performance_summary?.sharpe_ratio?.toFixed(2)}</div>
                <div className="text-[9px] text-gray-400 font-bold uppercase">Sharpe</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-black text-rose-400">-{Math.abs(selectedStrategy?.performance_summary?.max_drawdown || 0).toFixed(2)}%</div>
                <div className="text-[9px] text-gray-400 font-bold uppercase">Drawdown</div>
              </div>
              <div className="text-center border-l border-slate-200">
                <div className="text-lg font-black text-slate-500">{selectedStrategy?.performance_summary?.win_rate?.toFixed(2)}%</div>
                <div className="text-[9px] text-gray-400 font-bold uppercase">Win Rate</div>
              </div>
            </div>
          </div>

          <div>
            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 px-1">Share Note</div>
            <TextArea
              rows={4}
              value={shareNote}
              onChange={(e) => setShareNote(e.target.value)}
              placeholder="介绍一下您的策略灵感或最近的表现..."
              maxLength={500}
              showCount
              className="rounded-xl border-gray-200 focus:ring-4 focus:ring-blue-500/10 transition-all font-medium text-slate-600"
            />
          </div>

          {/* 标签选择 */}
          <div>
            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 px-1">Discoverable Tags</div>
            <TagSelector
              value={shareTags}
              onChange={setShareTags}
              mode="select"
              maxCount={10}
              placeholder="添加标签以获得更多曝光..."
              showCategories={true}
            />
          </div>

          <div className="bg-blue-50 p-4 rounded-xl flex items-start gap-3 border border-blue-100">
            <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center text-white text-[10px] font-black shrink-0 mt-0.5">!</div>
            <div className="text-xs text-blue-700 leading-relaxed font-medium">
              分享后，绩效摘要将在社区公开展示。您的核心配置和代码将保持私有，仅作为策略信号的展示。
            </div>
          </div>
        </div>
      </Modal>

      {/* 删除确认对话框 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <span>确认删除策略</span>
          </div>
        }
        open={deleteModalVisible}
        onOk={handleConfirmDelete}
        onCancel={() => {
          setDeleteModalVisible(false);
          setStrategyToDelete(null);
        }}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        {strategyToDelete && (
          <div className="space-y-3">
            <p>确定要删除以下策略吗？</p>
            <div className="bg-gray-50 p-3 rounded-lg">
              <div className="font-semibold text-gray-800 mb-2">{strategyToDelete.name || strategyToDelete.strategy_name}</div>
              <div className="text-sm text-gray-600 space-y-1">
                <div>状态: {getStatusTag(strategyToDelete.status)}</div>
                <div>创建时间: {new Date(strategyToDelete.created_at).toLocaleString('zh-CN')}</div>
                {strategyToDelete.performance_summary && (
                  <div className="mt-2 pt-2 border-t border-gray-200">
                    <div>收益率: {strategyToDelete.performance_summary.total_return_pct?.toFixed(2)}%</div>
                    <div>夏普比率: {strategyToDelete.performance_summary.sharpe_ratio?.toFixed(2)}</div>
                  </div>
                )}
              </div>
            </div>
            <div className="bg-red-50 p-3 rounded-lg text-sm text-red-700">
              <p className="font-semibold">⚠️ 警告</p>
              <p className="mt-1">删除后无法恢复，所有相关数据（包括回测记录）将被永久删除。</p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default StrategiesPage;
