import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Row, Space, Spin, Statistic, Table, Tag, message } from 'antd';
import { CloudDownloadOutlined, DatabaseOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { adminService } from '../services/adminService';
import { AdminDataStatusInvalidSample, AdminDataStatusOlderSample, AdminDataStatusResult } from '../types';

export const AdminDataManagement: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState(false);
    const [data, setData] = useState<AdminDataStatusResult | null>(null);

    const loadDataStatus = async (refresh = false) => {
        setLoading(true);
        try {
            const resp = await adminService.getDataStatus(refresh);
            setData(resp);
            if (refresh) {
                message.success(resp.message || '已触发后台扫描任务，请稍后再次刷新查看完整结果。');
            } else if (resp.from_cache) {
                // message.info('从缓存加载数据状态');
            }
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`加载数据状态失败: ${msg}`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDataStatus();
    }, []);

    const handleSyncMarketData = async () => {
        setSyncing(true);
        const hide = message.loading('正在从 Baostock 同步 market_data_daily ...', 0);
        try {
            const resp = await adminService.syncMarketDataDaily({ apply: true });
            hide();
            if (!resp.success) {
                message.error(`同步失败: ${resp.error || '脚本执行失败'}`);
                return;
            }
            if (resp.async) {
                message.success('同步任务已提交至后台处理，请稍后刷新查看数据状态。');
            } else {
                const r = resp.result || {};
                message.success(
                    `同步完成：${r.effective_trade_date || '-'}，成功 ${r.symbols_ok ?? 0}，失败 ${r.symbols_failed ?? 0}`,
                );
                await loadDataStatus();
            }
        } catch (err: unknown) {
            hide();
            const msg = err instanceof Error ? err.message : '未知错误';
            message.error(`同步失败: ${msg}`);
        } finally {
            setSyncing(false);
        }
    };

    const coverageRate = useMemo(() => {
        const c = data?.qlib_data?.latest_date_coverage;
        if (!c) return 0;
        const total = c.at_target_count + c.older_count + c.invalid_count;
        if (total <= 0) return 0;
        return Math.round((c.at_target_count / total) * 10000) / 100;
    }, [data]);

    const qlib = data?.qlib_data;
    const db = data?.market_data_daily;
    const checkedAt = data?.checked_at ? dayjs(data.checked_at).format('YYYY-MM-DD HH:mm:ss') : '—';
    const olderSamples = qlib?.topn_samples?.older_samples || [];
    const invalidSamples = qlib?.topn_samples?.invalid_samples || [];
    const sampleSize = qlib?.topn_samples?.sample_size || 20;

    const olderColumns = [
        {
            title: '标的',
            dataIndex: 'symbol',
            key: 'symbol',
            width: 140,
            render: (v: string) => <span className="font-mono font-bold">{v}</span>,
        },
        {
            title: '最后日期',
            dataIndex: 'last_date',
            key: 'last_date',
            width: 140,
        },
        {
            title: '滞后交易日数',
            dataIndex: 'lag_days',
            key: 'lag_days',
            width: 120,
            render: (v: number) => <Tag color={v > 60 ? 'red' : v > 10 ? 'orange' : 'gold'}>{v}</Tag>,
        },
    ];

    const invalidColumns = [
        {
            title: '标的',
            dataIndex: 'symbol',
            key: 'symbol',
            width: 140,
            render: (v: string) => <span className="font-mono font-bold">{v}</span>,
        },
        {
            title: '原因',
            dataIndex: 'reason',
            key: 'reason',
            width: 220,
            render: (v: string) => <Tag color="red">{v}</Tag>,
        },
        {
            title: '文件',
            dataIndex: 'file',
            key: 'file',
            ellipsis: true as const,
            render: (v?: string) => v || '—',
        },
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-xl font-black text-slate-800 tracking-tight">数据管理</h3>
                    <p className="text-slate-400 text-xs mt-1 italic">查看 Qlib 文件数据与 market_data_daily 实时状态</p>
                </div>
                <Space>
                    <Tag color="blue">检查时间: {checkedAt}</Tag>
                    <Button
                        icon={<CloudDownloadOutlined />}
                        className="rounded-xl h-10 px-5 border-slate-200 text-slate-700 font-bold"
                        loading={syncing}
                        onClick={handleSyncMarketData}
                    >
                        从Baostock补基础数据
                    </Button>
                    <Button
                        type="primary"
                        icon={<ReloadOutlined />}
                        className="rounded-xl h-10 px-5 bg-orange-600 border-none font-bold"
                        loading={loading || syncing}
                        onClick={() => loadDataStatus(true)}
                    >
                        强制刷新
                    </Button>
                    <Button
                        icon={<ReloadOutlined />}
                        className="rounded-xl h-10 px-5 border-slate-200 text-slate-700 font-bold"
                        loading={loading || syncing}
                        onClick={() => loadDataStatus(false)}
                    >
                        刷新
                    </Button>
                </Space>
            </div>

            {loading && !data ? (
                <div className="h-48 flex items-center justify-center">
                    <Spin />
                </div>
            ) : null}

            {data ? (
                <>
                    <Row gutter={16}>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="Qlib 最新交易日" value={qlib?.calendar_last_date || '—'} />
                            </Card>
                        </Col>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="market_data 最新交易日" value={db?.latest_trade_date || '—'} />
                            </Card>
                        </Col>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="今日入库行数" value={db?.today_rows ?? 0} />
                            </Card>
                        </Col>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="最新日覆盖率 (SH/SZ)" value={coverageRate} suffix="%" />
                            </Card>
                        </Col>
                    </Row>

                    {!qlib?.exists ? (
                        <Alert
                            type="error"
                            showIcon
                            message="未检测到 qlib_data 目录"
                            description={qlib?.qlib_dir || '路径未知'}
                        />
                    ) : null}
                    {db?.error ? (
                        <Alert type="warning" showIcon message="market_data_daily 查询异常" description={db.error} />
                    ) : null}

                    <Card
                        variant="borderless"
                        className="rounded-2xl shadow-sm"
                        title={
                            <Space>
                                <DatabaseOutlined />
                                <span className="font-bold">Qlib 数据概览</span>
                            </Space>
                        }
                    >
                        <Descriptions column={2} size="small" bordered>
                            <Descriptions.Item label="Qlib 路径">{qlib?.qlib_dir || '—'}</Descriptions.Item>
                            <Descriptions.Item label="交易日总数">{qlib?.calendar_total_days ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="日历开始">{qlib?.calendar_start_date || '—'}</Descriptions.Item>
                            <Descriptions.Item label="日历结束">{qlib?.calendar_last_date || '—'}</Descriptions.Item>
                            <Descriptions.Item label="标的总数">{qlib?.instruments?.total ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="特征目录总数">{qlib?.feature_dirs_total ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="SH 标的">{qlib?.instruments?.sh ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="SZ 标的">{qlib?.instruments?.sz ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="BJ 标的">{qlib?.instruments?.bj ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="其它标的">{qlib?.instruments?.other ?? 0}</Descriptions.Item>
                        </Descriptions>
                    </Card>

                    <Card variant="borderless" className="rounded-2xl shadow-sm" title={<span className="font-bold">最新交易日覆盖</span>}>
                        <Descriptions column={2} size="small" bordered>
                            <Descriptions.Item label="目标日期">
                                {qlib?.latest_date_coverage?.target_date || '—'}
                            </Descriptions.Item>
                            <Descriptions.Item label="已覆盖 (at_target)">
                                {qlib?.latest_date_coverage?.at_target_count ?? 0}
                            </Descriptions.Item>
                            <Descriptions.Item label="较旧 (older)">
                                {qlib?.latest_date_coverage?.older_count ?? 0}
                            </Descriptions.Item>
                            <Descriptions.Item label="无效 (invalid)">
                                {qlib?.latest_date_coverage?.invalid_count ?? 0}
                            </Descriptions.Item>
                        </Descriptions>
                    </Card>

                    <Card variant="borderless" className="rounded-2xl shadow-sm" title={<span className="font-bold">数据库数据状态</span>}>
                        <Descriptions column={2} size="small" bordered>
                            <Descriptions.Item label="系统交易日">{db?.trade_date || '—'}</Descriptions.Item>
                            <Descriptions.Item label="最新交易日">{db?.latest_trade_date || '—'}</Descriptions.Item>
                            <Descriptions.Item label="最新更新时间">{db?.latest_updated_at || '—'}</Descriptions.Item>
                            <Descriptions.Item label="今日行数">{db?.today_rows ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="feature_* 列数">{db?.feature_column_count ?? 0}</Descriptions.Item>
                            <Descriptions.Item label="是否与今日一致">
                                {(db?.latest_trade_date || '') === (db?.trade_date || '') ? (
                                    <Tag color="green">一致</Tag>
                                ) : (
                                    <Tag color="orange">不一致</Tag>
                                )}
                            </Descriptions.Item>
                        </Descriptions>
                    </Card>

                    <Row gutter={16}>
                        <Col span={12}>
                            <Card
                                variant="borderless"
                                className="rounded-2xl shadow-sm"
                                title={<span className="font-bold">异常标的 Top{sampleSize}：数据滞后（older）</span>}
                            >
                                <Table<AdminDataStatusOlderSample>
                                    size="small"
                                    pagination={false}
                                    rowKey={(r) => `${r.symbol}-${r.last_date}`}
                                    dataSource={olderSamples}
                                    columns={olderColumns}
                                    locale={{ emptyText: '暂无滞后样本' }}
                                    scroll={{ y: 320 }}
                                />
                            </Card>
                        </Col>
                        <Col span={12}>
                            <Card
                                variant="borderless"
                                className="rounded-2xl shadow-sm"
                                title={<span className="font-bold">异常标的 Top{sampleSize}：结构异常（invalid）</span>}
                            >
                                <Table<AdminDataStatusInvalidSample>
                                    size="small"
                                    pagination={false}
                                    rowKey={(r) => `${r.symbol}-${r.reason}-${r.file || ''}`}
                                    dataSource={invalidSamples}
                                    columns={invalidColumns}
                                    locale={{ emptyText: '暂无无效样本' }}
                                    scroll={{ y: 320 }}
                                />
                            </Card>
                        </Col>
                    </Row>
                </>
            ) : null}
        </div>
    );
};
