import React, { useState, useMemo } from 'react';
import { Button, List, Modal, Input, Steps, Alert, message, Tag, Progress } from 'antd';
import { MobileOutlined, LockOutlined, SafetyCertificateOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { userCenterService } from '../services/userCenterService';
import { useProfile } from '../hooks';

interface SecuritySettingsProps {
    userId: string;
}

export const SecuritySettings: React.FC<SecuritySettingsProps> = ({ userId }) => {
    const { profile, refetch } = useProfile(userId);
    const [phoneModalOpen, setPhoneModalOpen] = useState(false);
    const [phoneMode, setPhoneMode] = useState<'bind' | 'change'>('bind');
    const [phoneStep, setPhoneStep] = useState(0);
    const [loading, setLoading] = useState(false);

    // Password Form State
    const [passModalOpen, setPassModalOpen] = useState(false);
    const [oldPassword, setOldPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    
    // 密码强度检查
    const passwordChecks = useMemo(() => ({
        length: newPassword.length >= 8,
        upper: /[A-Z]/.test(newPassword),
        lower: /[a-z]/.test(newPassword),
        digit: /\d/.test(newPassword),
    }), [newPassword]);
    
    const passwordStrength = useMemo(() => {
        const score = Object.values(passwordChecks).filter(Boolean).length;
        return score;
    }, [passwordChecks]);

    // Phone Form State
    const [bindPhone, setBindPhone] = useState('');
    const [bindCode, setBindCode] = useState('');
    const [oldPhoneCode, setOldPhoneCode] = useState('');
    const [newPhone, setNewPhone] = useState('');
    const [newPhoneCode, setNewPhoneCode] = useState('');

    const openPhoneModal = () => {
        const hasPhone = !!(profile?.phone && String(profile.phone).trim());
        setPhoneMode(hasPhone ? 'change' : 'bind');
        setPhoneStep(0);
        // Reset fields
        setBindPhone('');
        setBindCode('');
        setOldPhoneCode('');
        setNewPhone('');
        setNewPhoneCode('');
        setPhoneModalOpen(true);
    };

    const sendCode = async (type: 'bind_phone' | 'change_phone_old' | 'change_phone_new', phone?: string) => {
        try {
            setLoading(true);
            await userCenterService.sendPhoneCode(type, phone);
            message.success('验证码已发送');
        } catch (error: any) {
            message.error(error.message || '发送失败');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async () => {
        try {
            setLoading(true);
            if (phoneMode === 'bind') {
                if (!bindPhone || !bindCode) return message.warning('请填写完整');
                await userCenterService.bindPhone(bindPhone, bindCode);
                message.success('绑定成功');
            } else {
                if (!oldPhoneCode || !newPhone || !newPhoneCode) return message.warning('请填写完整');
                await userCenterService.changePhone(oldPhoneCode, newPhone, newPhoneCode);
                message.success('换绑成功');
            }
            setPhoneModalOpen(false);
            refetch();
        } catch (error: any) {
            message.error(error.message || '操作失败');
        } finally {
            setLoading(false);
        }
    };

    const handlePasswordSubmit = async () => {
        if (!oldPassword) return message.warning('请输入当前密码');
        if (!newPassword) return message.warning('请输入新密码');
        if (!confirmPassword) return message.warning('请确认新密码');
        if (newPassword !== confirmPassword) return message.warning('两次输入的新密码不一致');
        if (passwordStrength < 4) return message.warning('新密码不符合安全要求');
        if (oldPassword === newPassword) return message.warning('新密码不能与当前密码相同');
        try {
            setLoading(true);
            await userCenterService.changePassword(oldPassword, newPassword);
            message.success('密码修改成功，请使用新密码登录');
            setPassModalOpen(false);
            setOldPassword('');
            setNewPassword('');
            setConfirmPassword('');
        } catch (error: any) {
            const errMsg = error.message || '密码修改失败';
            if (errMsg.includes('旧密码错误') || errMsg.includes('当前密码')) {
                message.error('当前密码输入错误，请重新输入');
            } else if (errMsg.includes('相同')) {
                message.error('新密码不能与当前密码相同');
            } else {
                message.error(errMsg);
            }
        } finally {
            setLoading(false);
        }
    };

    const data = [
        {
            title: '登录密码',
            description: '已设置。建议定期更换密码以保障账户安全。',
            icon: <LockOutlined className="text-blue-500 text-xl" />,
            action: <Button onClick={() => setPassModalOpen(true)}>修改</Button>
        },
        {
            title: '手机绑定',
            description: profile?.phone ? `已绑定手机：${profile.phone}` : '未绑定手机，绑定后可用于登录和找回密码。',
            icon: <MobileOutlined className="text-blue-500 text-xl" />,
            action: (
                <Button onClick={openPhoneModal}>
                    {profile?.phone ? '换绑' : '绑定'}
                </Button>
            )
        }
    ];

    return (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h3 className="text-lg font-bold text-slate-800 mb-6">安全设置</h3>
            <List
                itemLayout="horizontal"
                dataSource={data}
                renderItem={(item) => (
                    <List.Item actions={[item.action]}>
                        <List.Item.Meta
                            avatar={<div className="p-3 bg-blue-50 rounded-lg">{item.icon}</div>}
                            title={<span className="font-bold text-slate-700">{item.title}</span>}
                            description={item.description}
                        />
                    </List.Item>
                )}
            />

            <Modal
                title="修改登录密码"
                open={passModalOpen}
                onCancel={() => setPassModalOpen(false)}
                footer={null}
                destroyOnHidden
            >
                <div className="flex flex-col gap-4 py-4">
                    <div className="space-y-2">
                        <span className="text-xs font-bold text-slate-500">当前密码</span>
                        <Input.Password
                            placeholder="请输入当前登录密码"
                            value={oldPassword}
                            onChange={e => setOldPassword(e.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <span className="text-xs font-bold text-slate-500">新密码</span>
                        <Input.Password
                            placeholder="请输入新密码"
                            value={newPassword}
                            onChange={e => setNewPassword(e.target.value)}
                        />
                        {newPassword && (
                            <div className="mt-2 space-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-slate-500">密码强度：</span>
                                    <Progress 
                                        percent={passwordStrength * 25} 
                                        size="small" 
                                        showInfo={false}
                                        strokeColor={passwordStrength <= 1 ? '#ff4d4f' : passwordStrength <= 2 ? '#faad14' : passwordStrength <= 3 ? '#52c41a' : '#1890ff'}
                                        className="flex-1"
                                    />
                                    <span className={`text-xs font-medium ${
                                        passwordStrength <= 1 ? 'text-red-500' : 
                                        passwordStrength <= 2 ? 'text-orange-500' : 
                                        passwordStrength <= 3 ? 'text-green-500' : 'text-blue-500'
                                    }`}>
                                        {passwordStrength <= 1 ? '弱' : passwordStrength <= 2 ? '中' : passwordStrength <= 3 ? '强' : '很强'}
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-1 text-xs">
                                    <div className={`flex items-center gap-1 ${passwordChecks.length ? 'text-green-600' : 'text-slate-400'}`}>
                                        {passwordChecks.length ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                        <span>至少8位字符</span>
                                    </div>
                                    <div className={`flex items-center gap-1 ${passwordChecks.upper ? 'text-green-600' : 'text-slate-400'}`}>
                                        {passwordChecks.upper ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                        <span>包含大写字母</span>
                                    </div>
                                    <div className={`flex items-center gap-1 ${passwordChecks.lower ? 'text-green-600' : 'text-slate-400'}`}>
                                        {passwordChecks.lower ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                        <span>包含小写字母</span>
                                    </div>
                                    <div className={`flex items-center gap-1 ${passwordChecks.digit ? 'text-green-600' : 'text-slate-400'}`}>
                                        {passwordChecks.digit ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                        <span>包含数字</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                    <div className="space-y-2">
                        <span className="text-xs font-bold text-slate-500">确认新密码</span>
                        <Input.Password
                            placeholder="请再次输入新密码"
                            value={confirmPassword}
                            onChange={e => setConfirmPassword(e.target.value)}
                            status={confirmPassword && newPassword !== confirmPassword ? 'error' : undefined}
                        />
                        {confirmPassword && newPassword !== confirmPassword && (
                            <span className="text-xs text-red-500">两次输入的密码不一致</span>
                        )}
                    </div>
                    <Alert
                        type="info"
                        showIcon
                        message="修改成功后需要重新登录"
                    />
                    <div className="flex justify-end gap-2 mt-4">
                        <Button onClick={() => setPassModalOpen(false)}>取消</Button>
                        <Button 
                            type="primary" 
                            onClick={handlePasswordSubmit} 
                            loading={loading}
                            disabled={passwordStrength < 4}
                        >
                            提交修改
                        </Button>
                    </div>
                </div>
            </Modal>

            <Modal
                title={phoneMode === 'bind' ? '绑定手机号' : '更换手机号'}
                open={phoneModalOpen}
                onCancel={() => setPhoneModalOpen(false)}
                footer={null}
                destroyOnHidden
            >
                <div className="flex flex-col gap-4 py-4">
                    {phoneMode === 'change' && (
                        <Steps
                            size="small"
                            current={phoneStep}
                            items={[{ title: '验证旧手机' }, { title: '验证新手机' }]}
                            className="mb-4"
                        />
                    )}

                    {phoneMode === 'bind' ? (
                        <>
                            <Input
                                placeholder="请输入手机号"
                                value={bindPhone}
                                onChange={e => setBindPhone(e.target.value)}
                            />
                            <div className="flex gap-2 items-center">
                                <Input
                                    placeholder="验证码"
                                    value={bindCode}
                                    style={{ flex: 1 }}
                                    onChange={e => setBindCode(e.target.value)}
                                />
                                <Button 
                                    loading={loading} 
                                    onClick={() => sendCode('bind_phone', bindPhone)}
                                    style={{ width: 100 }}
                                >
                                    发送验证码
                                </Button>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col gap-4">
                            <div className="p-3 bg-orange-50 text-orange-600 text-xs rounded-lg">
                                为了您的账户安全，更换手机号需要验证旧手机号。
                            </div>

                            <div className="space-y-2">
                                <span className="text-xs font-bold text-slate-500">验证旧手机号 ({profile?.phone})</span>
                                <div className="flex gap-2 items-center">
                                    <Input
                                        placeholder="旧手机验证码"
                                        value={oldPhoneCode}
                                        style={{ flex: 1 }}
                                        onChange={e => setOldPhoneCode(e.target.value)}
                                    />
                                    <Button 
                                        loading={loading} 
                                        onClick={() => sendCode('change_phone_old')}
                                        style={{ width: 100 }}
                                    >
                                        发送验证码
                                    </Button>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <span className="text-xs font-bold text-slate-500">绑定新手机号</span>
                                <Input
                                    placeholder="新手机号"
                                    value={newPhone}
                                    onChange={e => setNewPhone(e.target.value)}
                                />
                                <div className="flex gap-2 items-center">
                                    <Input
                                        placeholder="新手机验证码"
                                        value={newPhoneCode}
                                        style={{ flex: 1 }}
                                        onChange={e => setNewPhoneCode(e.target.value)}
                                    />
                                    <Button 
                                        loading={loading} 
                                        onClick={() => sendCode('change_phone_new', newPhone)}
                                        style={{ width: 100 }}
                                    >
                                        发送验证码
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}

                    <div className="flex justify-end gap-2 mt-4">
                        <Button onClick={() => setPhoneModalOpen(false)}>取消</Button>
                        <Button type="primary" onClick={handleSubmit} loading={loading}>
                            提交
                        </Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
};
