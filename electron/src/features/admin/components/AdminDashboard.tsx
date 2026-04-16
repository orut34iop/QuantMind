import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Spin, message, Result, Button } from 'antd';
import { UserOutlined, LineChartOutlined, MessageOutlined, HeartOutlined, LoginOutlined, HomeOutlined } from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { adminService } from '../services/adminService';
import { authService } from '../../auth/services/authService';
import { useAppDispatch } from '../../../store';
import { logout } from '../../auth/store/authSlice';
import { DashboardMetrics } from '../types';

export const AdminDashboard: React.FC = () => {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const location = useLocation();
    const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [authError, setAuthError] = useState<{ status: number; message: string } | null>(null);

    useEffect(() => {
        loadMetrics();
    }, []);

    const loadMetrics = async () => {
        try {
            adminService.clearMetricsUnauthorized();
            setAuthError(null);
            const data = await adminService.getMetrics();
            setMetrics(data);
        } catch (err: any) {
            const status = err?.response?.status;
            const isLocked = String(err?.message || '').includes('ADMIN_METRICS_UNAUTHORIZED_LOCKED');
            const isAuthError = isLocked || status === 401 || status === 403 || (axios.isAxiosError(err) && (err.response?.status === 401 || err.response?.status === 403));
            
            if (isAuthError) {
                adminService.markMetricsUnauthorized();
                setAuthError({
                    status: status || 401,
                    message: status === 403 ? '您没有访问管理面板的权限。' : '您的登录会话已过期，请重新登录。'
                });
                return;
            }
            message.error('加载系统指标失败');
        } finally {
            setLoading(false);
        }
    };

    if (authError) {
        return (
            <div className="flex items-center justify-center py-20 bg-white rounded-3xl overflow-hidden">
                <Result
                    status={authError.status === 403 ? '403' : '403'} // AntD 403 is good for both Auth/Authz errors
                    title={authError.status === 403 ? '访问受限' : '会话过期'}
                    subTitle={authError.message}
                    extra={[
                        <Button 
                            type="primary" 
                            key="login" 
                            icon={<LoginOutlined />}
                            size="large"
                            className="rounded-xl px-8"
                            onClick={async () => {
                                await dispatch(logout());
                                navigate('/auth/login', { state: { from: location } });
                            }}
                        >
                            重新登录
                        </Button>,
                        <Button 
                            key="home" 
                            icon={<HomeOutlined />}
                            size="large"
                            className="rounded-xl px-8"
                            onClick={() => navigate('/')}
                        >
                            返回首页
                        </Button>
                    ]}
                />
            </div>
        );
    }

    if (loading || !metrics) return <Spin size="large" className="w-full flex justify-center py-20" />;

    return (
        <div className="admin-dashboard-view space-y-6">
            <Row gutter={[16, 16]}>
                <Col span={6}>
                    <Card hoverable className="rounded-2xl border-slate-100 shadow-sm">
                        <Statistic
                            title="总用户数"
                            value={metrics.users.total}
                            prefix={<UserOutlined className="text-blue-500" />}
                        />
                        <div className="text-xs text-slate-400 mt-2">
                            今日新增: <span className="text-emerald-500 font-bold">+{metrics.users.new_today}</span>
                        </div>
                    </Card>
                </Col>
                <Col span={6}>
                    <Card hoverable className="rounded-2xl border-slate-100 shadow-sm">
                        <Statistic
                            title="运行策略"
                            value={metrics.strategies.live}
                            prefix={<LineChartOutlined className="text-indigo-500" />}
                        />
                        <div className="text-xs text-slate-400 mt-2">
                            总策略: {metrics.strategies.total}
                        </div>
                    </Card>
                </Col>
                <Col span={6}>
                    <Card hoverable className="rounded-2xl border-slate-100 shadow-sm">
                        <Statistic
                            title="社区动态"
                            value={metrics.content.posts}
                            prefix={<MessageOutlined className="text-amber-500" />}
                        />
                        <div className="text-xs text-slate-400 mt-2">
                            评论数: {metrics.content.comments}
                        </div>
                    </Card>
                </Col>
                <Col span={6}>
                    <Card hoverable className="rounded-2xl border-slate-100 shadow-sm">
                        <Statistic
                            title="系统健康度"
                            value={metrics.system.health_score}
                            suffix="/ 100"
                            valueStyle={{ color: metrics.system.health_score > 90 ? '#10b981' : '#f59e0b' }}
                        />
                        <div className="text-xs text-slate-400 mt-2">
                            保持运行: {metrics.system.uptime_days} 天
                        </div>
                    </Card>
                </Col>
            </Row>

            <Card title="系统运行状态" className="rounded-2xl border-slate-100 shadow-sm">
                <div className="p-10 text-center text-slate-400 border-2 border-dashed border-slate-100 rounded-xl">
                    <HeartOutlined className="text-4xl mb-4 text-emerald-100" />
                    <p>核心服务集群 `api`, `trade`, `engine`, `stream` 运行正常</p>
                    <div className="flex justify-center gap-4 mt-4">
                        {['api', 'trade', 'engine', 'stream'].map(s => (
                            <span key={s} className="px-3 py-1 bg-emerald-50 text-emerald-600 rounded-full text-[10px] uppercase font-bold border border-emerald-100">
                                {s}: online
                            </span>
                        ))}
                    </div>
                </div>
            </Card>
        </div>
    );
};
