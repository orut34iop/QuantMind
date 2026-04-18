import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Descriptions, Row, Space, Spin, Statistic, Table, Tag, message } from 'antd';
import { DatabaseOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { adminService } from '../services/adminService';
import {
    AdminFeatureSnapshotsOlderSample,
    AdminFeatureSnapshotsInvalidSample,
    AdminDataStatusResult
} from '../types';

export const AdminDataManagement: React.FC = () => {
    const [loading, setLoading] = useState(false);
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

    const qlib = data?.qlib_data;
    const snapshots = data?.feature_snapshots;
    const checkedAt = data?.checked_at ? dayjs(data.checked_at).format('YYYY-MM-DD HH:mm:ss') : '—';
    const olderSamples = snapshots?.topn_samples?.older_samples || [];
    const invalidSamples = snapshots?.topn_samples?.invalid_samples || [];
    const sampleSize = snapshots?.topn_samples?.sample_size || 20;

    const coverageRate = useMemo(() => {
        const c = snapshots?.latest_date_coverage;
        if (!c) return 0;
        const total = c.at_target_count + c.older_count + c.invalid_count;
        if (total <= 0) return 0;
        return Math.round((c.at_target_count / total) * 10000) / 100;
    }, [snapshots]);

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
                    <p className="text-slate-400 text-xs mt-1 italic">查看 Qlib 文件数据与特征快照状态</p>
                </div>
                <Space>
                    <Tag color="blue">检查时间: {checkedAt}</Tag>
                    <Button
                        type="primary"
                        icon={<ReloadOutlined />}
                        className="rounded-xl h-10 px-5 bg-orange-600 border-none font-bold"
                        loading={loading}
                        onClick={() => loadDataStatus(true)}
                    >
                        强制刷新
                    </Button>
                    <Button
                        icon={<ReloadOutlined />}
                        className="rounded-xl h-10 px-5 border-slate-200 text-slate-700 font-bold"
                        loading={loading}
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
                                <Statistic title="特征快照最新日期" value={snapshots?.max_date || '—'} />
                            </Card>
                        </Col>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="Parquet 文件数" value={snapshots?.file_count ?? 0} />
                            </Card>
                        </Col>
                        <Col span={6}>
                            <Card variant="borderless" className="rounded-2xl shadow-sm">
                                <Statistic title="最新日覆盖率" value={coverageRate} suffix="%" />
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
                    {!snapshots?.exists ? (
                        <Alert
                            type="warning"
                            showIcon
                            message="未检测到 feature_snapshots 目录"
                            description={snapshots?.snapshot_dir || '路径未知'}
                        />
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

                    <Card
                        variant="borderless"
                        className="rounded-2xl shadow-sm"
                        title={
                            <Space>
                                <DatabaseOutlined />
                                <span className="font-bold">特征快照概览</span>
                            </Space>
                        }
                    >
                        {!snapshots?.exists ? (
                            <Alert type="warning" showIcon message="目录不存在或无 parquet 文件" />
                        ) : (
                            <>
                                <Descriptions column={2} size="small" bordered>
                                    <Descriptions.Item label="快照目录">{snapshots?.snapshot_dir || '—'}</Descriptions.Item>
                                    <Descriptions.Item label="Parquet 文件数">{snapshots?.file_count ?? 0}</Descriptions.Item>
                                    <Descriptions.Item label="成功扫描">{snapshots?.scanned_files ?? 0}</Descriptions.Item>
                                    <Descriptions.Item label="扫描失败">{snapshots?.failed_files ?? 0}</Descriptions.Item>
                                    <Descriptions.Item label="数据开始日期">{snapshots?.min_date || '—'}</Descriptions.Item>
                                    <Descriptions.Item label="数据结束日期">{snapshots?.max_date || '—'}</Descriptions.Item>
                                    <Descriptions.Item label="总行数">{snapshots?.total_rows?.toLocaleString() ?? 0}</Descriptions.Item>
                                    <Descriptions.Item label="错误">
                                        {snapshots?.error ? <Tag color="red">{snapshots.error}</Tag> : <Tag color="green">无</Tag>}
                                    </Descriptions.Item>
                                </Descriptions>

                                {snapshots?.suggested_periods ? (
                                    <div className="mt-4">
                                        <h4 className="font-bold text-slate-700 mb-2">建议训练/验证/测试划分</h4>
                                        <Descriptions column={3} size="small" bordered>
                                            <Descriptions.Item label="训练集">
                                                {snapshots.suggested_periods.train[0]} ~ {snapshots.suggested_periods.train[1]}
                                            </Descriptions.Item>
                                            <Descriptions.Item label="验证集">
                                                {snapshots.suggested_periods.val[0]} ~ {snapshots.suggested_periods.val[1]}
                                            </Descriptions.Item>
                                            <Descriptions.Item label="测试集">
                                                {snapshots.suggested_periods.test[0]} ~ {snapshots.suggested_periods.test[1]}
                                            </Descriptions.Item>
                                        </Descriptions>
                                    </div>
                                ) : null}
                            </>
                        )}
                    </Card>

                    {snapshots?.exists && snapshots.latest_date_coverage ? (
                        <Card variant="borderless" className="rounded-2xl shadow-sm" title={<span className="font-bold">最新日期覆盖</span>}>
                            <Descriptions column={2} size="small" bordered>
                                <Descriptions.Item label="目标日期">
                                    {snapshots?.latest_date_coverage?.target_date || '—'}
                                </Descriptions.Item>
                                <Descriptions.Item label="已覆盖 (at_target)">
                                    {snapshots?.latest_date_coverage?.at_target_count ?? 0}
                                </Descriptions.Item>
                                <Descriptions.Item label="较旧 (older)">
                                    {snapshots?.latest_date_coverage?.older_count ?? 0}
                                </Descriptions.Item>
                                <Descriptions.Item label="无效 (invalid)">
                                    {snapshots?.latest_date_coverage?.invalid_count ?? 0}
                                </Descriptions.Item>
                            </Descriptions>
                        </Card>
                    ) : null}

                    {snapshots?.exists && (olderSamples.length > 0 || invalidSamples.length > 0) ? (
                        <Row gutter={16}>
                            <Col span={12}>
                                <Card
                                    variant="borderless"
                                    className="rounded-2xl shadow-sm"
                                    title={<span className="font-bold">异常标的 Top{sampleSize}：数据滞后（older）</span>}
                                >
                                    <Table<AdminFeatureSnapshotsOlderSample>
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
                                    title={<span className="font-bold">异常文件 Top{sampleSize}：读取失败（invalid）</span>}
                                >
                                    <Table<AdminFeatureSnapshotsInvalidSample>
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
                    ) : null}
                </>
            ) : null}
        </div>
    );
};
