import React, { useEffect, useState } from 'react';
import { Button, Card, DatePicker, Descriptions, Input, Modal, Space, Table, Tag, message } from 'antd';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { adminService } from '../services/adminService';
import { AdminPredictionDetailResult, AdminPredictionRunSummary } from '../types';

export const AdminPredictionManagement: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [detailLoading, setDetailLoading] = useState(false);
    const [items, setItems] = useState<AdminPredictionRunSummary[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [predictionDate, setPredictionDate] = useState<string>('');
    const [runId, setRunId] = useState<string>('');
    const [tenantId, setTenantId] = useState<string>('');
    const [userId, setUserId] = useState<string>('');
    const [detailVisible, setDetailVisible] = useState(false);
    const [detail, setDetail] = useState<AdminPredictionDetailResult | null>(null);
    const [exportLoading, setExportLoading] = useState<Record<string, boolean>>({});

    const loadRuns = async (nextPage = page, nextPageSize = pageSize) => {
        setLoading(true);
        try {
            const resp = await adminService.listPredictionRuns({
                predictionDate: predictionDate || undefined,
                runId: runId.trim() || undefined,
                tenantId: tenantId.trim() || undefined,
                userId: userId.trim() || undefined,
                page: nextPage,
                pageSize: nextPageSize,
            });
            setItems(resp.items || []);
            setTotal(resp.total || 0);
            setPage(resp.page || nextPage);
            setPageSize(resp.page_size || nextPageSize);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`加载预测批次失败: ${msg}`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadRuns(1, pageSize);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const openDetail = async (row: AdminPredictionRunSummary) => {
        setDetailLoading(true);
        setDetailVisible(true);
        try {
            const resp = await adminService.getPredictionRunDetail(row.run_id, {
                predictionDate: row.trade_date,
                tenantId: row.tenant_id,
                userId: row.user_id,
                page: 1,
                pageSize: 300,
            });
            setDetail(resp);
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`加载预测明细失败: ${msg}`);
            setDetail(null);
        } finally {
            setDetailLoading(false);
        }
    };

    const handleExport = async (row: AdminPredictionRunSummary) => {
        const key = `${row.run_id}-${row.trade_date}`;
        setExportLoading({ ...exportLoading, [key]: true });
        try {
            await adminService.downloadPredictionExport(row.run_id, {
                predictionDate: row.trade_date,
                tenantId: row.tenant_id,
                userId: row.user_id,
            });
            message.success('导出成功');
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`导出失败: ${msg}`);
        } finally {
            const next = { ...exportLoading };
            delete next[key];
            setExportLoading(next);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-xl font-black text-slate-800 tracking-tight">预测管理</h3>
                    <p className="text-slate-400 text-xs mt-1 italic">查询模型生成的预测批次与分数明细（默认保留 30 天）</p>
                </div>
                <Space>
                    <DatePicker
                        allowClear
                        placeholder="预测交易日"
                        value={predictionDate ? dayjs(predictionDate) : null}
                        onChange={(v) => setPredictionDate(v ? v.format('YYYY-MM-DD') : '')}
                    />
                    <Input
                        allowClear
                        placeholder="run_id"
                        value={runId}
                        onChange={(e) => setRunId(e.target.value)}
                        style={{ width: 260 }}
                    />
                    <Input
                        allowClear
                        placeholder="tenant_id"
                        value={tenantId}
                        onChange={(e) => setTenantId(e.target.value)}
                        style={{ width: 150 }}
                    />
                    <Input
                        allowClear
                        placeholder="user_id"
                        value={userId}
                        onChange={(e) => setUserId(e.target.value)}
                        style={{ width: 150 }}
                    />
                    <Button
                        type="primary"
                        icon={<SearchOutlined />}
                        onClick={() => loadRuns(1, pageSize)}
                        className="rounded-xl h-10 px-5 bg-slate-900 border-none font-bold"
                    >
                        查询
                    </Button>
                    <Button
                        icon={<ReloadOutlined />}
                        loading={loading}
                        onClick={() => loadRuns(page, pageSize)}
                        className="rounded-xl h-10 px-5 border-slate-200 text-slate-700 font-bold"
                    >
                        刷新
                    </Button>
                </Space>
            </div>

            <Card variant="borderless" className="rounded-2xl shadow-sm">
                <Table
                    rowKey={(r) => `${r.run_id}-${r.trade_date}-${r.user_id}`}
                    loading={loading}
                    dataSource={items}
                    pagination={{
                        current: page,
                        pageSize,
                        total,
                        showSizeChanger: true,
                        pageSizeOptions: [20, 50, 100],
                        onChange: (p, ps) => loadRuns(p, ps),
                    }}
                    scroll={{ x: 'max-content' }}
                    columns={[
                        {
                            title: '预测交易日',
                            dataIndex: 'trade_date',
                            width: 130,
                            render: (v: string) => <Tag color="blue">{v}</Tag>,
                        },
                        {
                            title: 'Run ID',
                            dataIndex: 'run_id',
                            ellipsis: true as const,
                            render: (v: string) => <span className="font-mono text-xs">{v}</span>,
                        },
                        {
                            title: '预测模型',
                            dataIndex: 'model_version',
                            width: 180,
                            render: (v: string) => <Tag color="geekblue">{v || 'inference_script'}</Tag>,
                        },
                        { title: '租户', dataIndex: 'tenant_id', width: 120 },
                        { title: '用户', dataIndex: 'user_id', width: 120 },
                        {
                            title: '条数',
                            dataIndex: 'rows_count',
                            width: 90,
                            align: 'right' as const,
                        },
                        {
                            title: '分数范围',
                            key: 'score_range',
                            width: 200,
                            render: (_: unknown, r: AdminPredictionRunSummary) => (
                                <span className="font-mono text-xs">
                                    {r.min_fusion_score ?? '—'} ~ {r.max_fusion_score ?? '—'}
                                </span>
                            ),
                        },
                        {
                            title: '写入时间',
                            dataIndex: 'last_created_at',
                            width: 180,
                            render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
                        },
                        {
                            title: '操作',
                            key: 'action',
                            width: 150,
                            align: 'center' as const,
                            render: (_: unknown, r: AdminPredictionRunSummary) => (
                                <Space split={null}>
                                    <Button type="link" size="small" onClick={() => openDetail(r)}>
                                        查看
                                    </Button>
                                    <Button 
                                        type="link" 
                                        size="small" 
                                        onClick={() => handleExport(r)}
                                        loading={exportLoading[`${r.run_id}-${r.trade_date}`]}
                                        className="text-emerald-600 hover:text-emerald-700"
                                    >
                                        导出
                                    </Button>
                                </Space>
                            ),
                        },
                    ]}
                />
            </Card>

            <Modal
                open={detailVisible}
                onCancel={() => setDetailVisible(false)}
                footer={null}
                width={980}
                title="预测批次明细"
                style={{ top: 24 }}
                styles={{
                    content: { marginBottom: 96 },
                    body: {
                        maxHeight: 'calc(100vh - 220px)',
                        overflowY: 'auto',
                        paddingBottom: 24,
                    },
                }}
            >
                {detail && (
                    <div className="space-y-4">
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                            <span className="text-slate-500 mr-2">预测模型：</span>
                            <span className="font-mono font-semibold text-slate-800">
                                {detail.summary.model_version || 'inference_script'}
                            </span>
                        </div>
                        <Descriptions size="small" bordered column={3}>
                            <Descriptions.Item label="Run ID" span={2}>
                                <span className="font-mono text-xs">{detail.summary.run_id}</span>
                            </Descriptions.Item>
                            <Descriptions.Item label="预测交易日">{detail.summary.trade_date}</Descriptions.Item>
                            <Descriptions.Item label="租户">{detail.summary.tenant_id}</Descriptions.Item>
                            <Descriptions.Item label="用户">{detail.summary.user_id}</Descriptions.Item>
                            <Descriptions.Item label="条数">{detail.summary.rows_count}</Descriptions.Item>
                            <Descriptions.Item label="分数最小值">{detail.summary.min_fusion_score ?? '—'}</Descriptions.Item>
                            <Descriptions.Item label="分数最大值">{detail.summary.max_fusion_score ?? '—'}</Descriptions.Item>
                            <Descriptions.Item label="写入时间" span={3}>
                                {detail.summary.last_created_at ? dayjs(detail.summary.last_created_at).format('YYYY-MM-DD HH:mm:ss') : '—'}
                            </Descriptions.Item>
                        </Descriptions>
                        <Table
                            rowKey={(r) => `${r.symbol}-${r.created_at}`}
                            loading={detailLoading}
                            dataSource={detail.items}
                            pagination={{ pageSize: 20 }}
                            columns={[
                                { title: '代码', dataIndex: 'symbol', width: 120, render: (v: string) => <span className="font-mono">{v}</span> },
                                { title: 'fusion_score', dataIndex: 'fusion_score', width: 140, render: (v: number | null) => (v == null ? '—' : v.toFixed(6)) },
                                { title: 'light_score', dataIndex: 'light_score', width: 120, render: (v: number | null) => (v == null ? '—' : v.toFixed(6)) },
                                { title: 'tft_score', dataIndex: 'tft_score', width: 120, render: (v: number | null) => (v == null ? '—' : v.toFixed(6)) },
                                { title: 'rank', dataIndex: 'score_rank', width: 90, render: (v: number | null) => (v == null ? '—' : v) },
                                { title: 'side', dataIndex: 'signal_side', width: 100, render: (v: string | null) => v || '—' },
                                {
                                    title: '写入时间',
                                    dataIndex: 'created_at',
                                    width: 180,
                                    render: (v: string | null) => (v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '—'),
                                },
                            ]}
                        />
                    </div>
                )}
            </Modal>
        </div>
    );
};
