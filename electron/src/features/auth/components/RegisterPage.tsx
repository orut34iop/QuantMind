/**
 * 注册页面组件
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Button,
  Alert,
  Spin,
  Typography,
  Divider,
  Progress,
  Space,
  Tooltip,
  message,
  Radio,
} from 'antd';
import {
  UserOutlined,
  MailOutlined,
  LockOutlined,
  PhoneOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { useAuth, useRegisterForm } from '../hooks/useAuth';
import { authService } from '../services/authService';
import { useAppDispatch } from '../../../store';
import { setUser } from '../store/authSlice';
import { validatePasswordStrength, createValidationRules, debounce, PHONE_REGEX } from '../utils/validation';
import { PageLoading } from './LoadingStates';
import type { RegisterData } from '../types/auth.types';

const { Title, Text } = Typography;

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const { register: handleRegister, isAuthenticated, isLoading } = useAuth();
  const {
    email,
    password,
    confirmPassword,
    full_name,
    phone,
    sms_verification_code,
    errors,
    updateField,
    setErrors,
    clearErrors,
    setEmail,
    setPassword,
    setConfirmPassword,
    setFullName,
    setPhone,
    setSmsVerificationCode,
  } = useRegisterForm();

  const [registerError, setRegisterError] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<any>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const dispatch = useAppDispatch();
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [confirmPasswordVisible, setConfirmPasswordVisible] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [sendingCode, setSendingCode] = useState(false);

  // 响应式设计
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 如果已经登录，重定向到个人中心
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/user-center');
    }
  }, [isAuthenticated, navigate]);

  // 初始化加载完成
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsInitialLoading(false);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // 密码强度检测（使用新的验证工具）
  const checkPasswordStrength = (password: string) => {
    if (!password) {
      setPasswordStrength(null);
      return;
    }

    const result = validatePasswordStrength(password);
    const levels = {
      weak: { color: '#ff4d4f', text: '弱', percent: 20 },
      medium: { color: '#ff7a45', text: '中等', percent: 40 },
      strong: { color: '#52c41a', text: '强', percent: 80 },
      'very-strong': { color: '#1890ff', text: '很强', percent: 100 },
    };

    const level = levels[result.level] || levels.weak;

    setPasswordStrength({
      score: result.score,
      level: result.level,
      color: level.color,
      text: level.text,
      percent: level.percent,
      feedback: result.feedback,
      passed: result.passed,
    });
  };

  // 实时验证字段
  const debouncedValidateField = useMemo(
    () => debounce((field: string, value: string) => {
      const result = createValidationRules(field, { username: '' })[0];
      if (result && result.validator) {
        result.validator({}, value).catch((error: string) => {
          if (error) {
            setErrors({ [field]: error });
          } else {
            setErrors({ [field]: '' });
          }
        });
      }
    }, 300),
    []
  );

  // 处理密码变化
  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newPassword = e.target.value;
    setPassword(newPassword);
    checkPasswordStrength(newPassword);

    // 实时验证密码
    debouncedValidateField('password', newPassword);

    // 实时验证确认密码
    if (confirmPassword && newPassword !== confirmPassword) {
      setErrors({ confirmPassword: '两次输入的密码不一致' });
    } else {
      setErrors({ confirmPassword: '' });
    }
  };

  // 处理确认密码变化
  const handleConfirmPasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newConfirmPassword = e.target.value;
    setConfirmPassword(newConfirmPassword);

    if (password && newConfirmPassword !== password) {
      setErrors({ confirmPassword: '两次输入的密码不一致' });
    } else {
      setErrors({ confirmPassword: '' });
    }
  };

  // 处理邮箱变化
  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    if (newEmail) debouncedValidateField('email', newEmail);
  };

  // 处理手机号变化
  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newPhone = e.target.value;
    setPhone(newPhone);
    debouncedValidateField('phone', newPhone);
  };

  // 倒计时效果
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (countdown > 0) {
      timer = setInterval(() => {
        setCountdown(countdown - 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [countdown]);

  // 发送验证码
  const getRegisterSmsFriendlyErrorMessage = (error: any): string => {
    const status = error?.response?.status;
    const data = error?.response?.data || {};
    const detail = String(data?.detail || data?.message || '').trim();
    const code = String(data?.error_code || data?.code || error?.code || '').trim().toUpperCase();

    if (status === 429 || code.includes('TOO_MANY') || detail.includes('频繁')) {
      return '发送过于频繁，请稍后再试';
    }
    if (detail.includes('今日发送次数已达上限')) {
      return '今日验证码发送次数已达上限，请明日再试';
    }
    if (status === 503 || detail.includes('短信服务配置缺失') || detail.includes('短信客户端未初始化') || detail.includes('短信服务依赖未安装')) {
      return '短信服务暂不可用，请联系管理员检查短信配置';
    }
    if (detail.includes('短信模板未配置')) {
      return '短信模板未配置，请联系管理员';
    }
    if (detail.includes('Redis 未就绪')) {
      return '系统限流服务未就绪，请稍后重试';
    }
    if (code === 'ERR_NETWORK' || error?.name === 'AxiosError' && !status) {
      return '网络连接失败，请检查网络后重试';
    }
    if (status === 400 && detail) {
      return detail;
    }
    if (detail) {
      return detail;
    }
    return error?.message || '发送验证码失败，请稍后重试';
  };

  const handleSendCode = async () => {
    if (countdown > 0) {
      message.warning(`请求过于频繁，请在 ${countdown} 秒后重试`);
      return;
    }
    if (!phone) {
      setErrors({ phone: '请输入手机号' });
      return;
    }
    if (errors.phone) {
      return;
    }

    try {
      setSendingCode(true);
      await authService.requestRegisterSmsCode(phone.trim());
      message.success('验证码已发送，请查收短信');
      setCountdown(60);
    } catch (error: any) {
      message.error(getRegisterSmsFriendlyErrorMessage(error));
    } finally {
      setSendingCode(false);
    }
  };

  // 处理注册表单提交
  const handleSubmit = async (values: any) => {
    try {
      setRegisterError(null);
      clearErrors();

      // 验证密码强度
      if (!passwordStrength || !passwordStrength.passed) {
        setRegisterError('密码强度不足，请设置更复杂的密码');
        message.error('密码强度不足，请设置更复杂的密码', 3);
        return;
      }

      // 验证密码匹配
      if (values.password !== values.confirmPassword) {
        setRegisterError('两次输入的密码不一致');
        message.error('两次输入的密码不一致', 3);
        return;
      }

      const registerData: RegisterData = {
        phone: values.phone.trim(),
        sms_verification_code: values.sms_verification_code.trim(),
        email: values.email?.trim() || undefined,
        password: values.password,
        confirmPassword: values.confirmPassword,
        full_name: values.full_name?.trim() || undefined,
      };

      try {
        await handleRegister(registerData);

        // 显示成功消息
        message.success('注册成功！正在跳转到个人中心...', 3);

        // 注册成功，自动跳转（由useAuth处理）
      } catch (e: any) {
        // 注册失败处理
        const errorMessage = e.message || '注册失败，请重试';
        setRegisterError(errorMessage);
        message.error(errorMessage, 3);
      }
    } catch (error: any) {
      const errorMessage = error.message || '注册失败，请重试';
      setRegisterError(errorMessage);
      message.error(errorMessage, 3);
    }
  };

  // 处理表单字段变化
  const handleFieldChange = (field: string, value: any) => {
    updateField(field, value);
    if (registerError) {
      setRegisterError(null);
    }
  };

  // 响应式样式
  const cardStyle = useMemo(() => ({
    width: '100%',
    maxWidth: isMobile ? '100%' : 480,
    borderRadius: isMobile ? 0 : '12px',
    boxShadow: isMobile ? 'none' : '0 8px 32px rgba(0, 0, 0, 0.1)',
    margin: isMobile ? 0 : 'auto',
  }), [isMobile]);

  const containerStyle = useMemo(() => ({
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: isMobile ? 0 : '20px',
  }), [isMobile]);

  // 初始加载状态
  if (isInitialLoading) {
    return <PageLoading message="初始化中..." />;
  }

  return (
    <div style={containerStyle}>
      <Card
        className="auth-rounded-card"
        style={cardStyle}
        styles={{
          body: {
            padding: isMobile ? '24px 20px' : '40px',
            borderRadius: 'inherit',
            overflow: 'hidden',
          }
        }}
      >
        {/* Logo 和标题 */}
        <div style={{ textAlign: 'center', marginBottom: isMobile ? '24px' : '32px' }}>
          <Title
            level={isMobile ? 4 : 3}
            style={{
              margin: 0,
              color: '#262626',
              fontSize: isMobile ? '20px' : '24px'
            }}
          >
            创建 QuantMind 账号
          </Title>
          <Text type="secondary" style={{ fontSize: '14px' }}>
            加入专业的量化交易平台
          </Text>
        </div>

        {/* 错误提示 */}
        {registerError && (
          <Alert
            message={registerError}
            type="error"
            showIcon
            closable
            onClose={() => setRegisterError(null)}
            style={{ marginBottom: '24px' }}
          />
        )}

        {/* 注册表单 */}
        <Form
          form={form}
          name="register"
          onFinish={handleSubmit}
          layout="vertical"
          requiredMark={false}
          disabled={isLoading}
          size={isMobile ? 'middle' : 'large'}
        >
          <Form.Item
            name="full_name"
            rules={[
              { required: true, whitespace: true, message: '请输入用户名' },
            ]}
            validateStatus={errors.full_name ? 'error' : undefined}
            help={errors.full_name}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              size={isMobile ? 'large' : 'large'}
              value={full_name}
              onChange={(e) => handleFieldChange('full_name', e.target.value)}
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="phone"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: PHONE_REGEX, message: '请输入有效的中国大陆手机号' },
            ]}
            validateStatus={errors.phone ? 'error' : undefined}
            help={errors.phone}
          >
            <Input
              prefix={<PhoneOutlined />}
              placeholder="手机号码"
              size={isMobile ? 'large' : 'large'}
              value={phone}
              onChange={handlePhoneChange}
              autoComplete="tel"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: '8px', width: '100%' }}>
              <Form.Item
                name="sms_verification_code"
                rules={[
                  { required: true, message: '请输入验证码' },
                  { len: 6, message: '请输入6位验证码' },
                ]}
                noStyle
              >
                <Input
                  prefix={<SafetyCertificateOutlined />}
                  placeholder="短信验证码"
                  size={isMobile ? 'large' : 'large'}
                  maxLength={6}
                  style={{ flex: 1 }}
                  value={sms_verification_code}
                  onChange={(e) => setSmsVerificationCode(e.target.value)}
                />
              </Form.Item>
              <Button
                size={isMobile ? 'large' : 'large'}
                onClick={handleSendCode}
                disabled={!!countdown || !full_name?.trim() || !phone || !!errors.phone}
                loading={sendingCode}
                style={{ width: '120px' }}
              >
                {countdown > 0 ? `${countdown}s` : '获取验证码'}
              </Button>
            </div>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {countdown > 0 ? `请在 ${countdown} 秒后重发验证码` : '未收到验证码可在60秒后重发'}
              </Text>
            </div>
          </Form.Item>

          <Form.Item
            name="email"
            rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
            validateStatus={errors.email ? 'error' : undefined}
            help={errors.email}
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="邮箱地址（可选）"
              size={isMobile ? 'large' : 'large'}
              value={email}
              onChange={handleEmailChange}
              autoComplete="email"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少8个字符' },
              {
                validator: (_, value) => {
                  const result = validatePasswordStrength(value);
                  return result.passed ? Promise.resolve() : Promise.reject(result.feedback[0]);
                }
              }
            ]}
            validateStatus={errors.password ? 'error' : undefined}
            help={errors.password}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size={isMobile ? 'large' : 'large'}
              value={password}
              onChange={handlePasswordChange}
              autoComplete="new-password"
              visibilityToggle={{
                visible: passwordVisible,
                onVisibleChange: setPasswordVisible,
              }}
              iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
            />
          </Form.Item>

          {/* 密码强度指示器 */}
          {password && passwordStrength && (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <Text style={{ fontSize: '12px', color: '#666' }}>密码强度</Text>
                <Text style={{ fontSize: '12px', color: passwordStrength.color }}>
                  {passwordStrength.text}
                </Text>
              </div>
              <Progress
                percent={passwordStrength.percent}
                strokeColor={passwordStrength.color}
                showInfo={false}
                size="small"
                style={{ marginBottom: '8px' }}
              />
              {passwordStrength.feedback && passwordStrength.feedback.length > 0 && (
                <div style={{ fontSize: '12px', color: '#ff4d4f' }}>
                  • {passwordStrength.feedback.join(' • ')}
                </div>
              )}
            </div>
          )}

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject('两次输入的密码不一致');
                },
              }),
            ]}
            validateStatus={errors.confirmPassword ? 'error' : undefined}
            help={errors.confirmPassword}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="确认密码"
              size={isMobile ? 'large' : 'large'}
              value={confirmPassword}
              onChange={handleConfirmPasswordChange}
              autoComplete="new-password"
              visibilityToggle={{
                visible: confirmPasswordVisible,
                onVisibleChange: setConfirmPasswordVisible,
              }}
              iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: '16px' }}>
            <Button
              type="primary"
              htmlType="submit"
              size={isMobile ? 'large' : 'large'}
              block
              loading={isLoading}
              style={{
                height: isMobile ? '44px' : '48px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #1890ff, #722ed1)',
                border: 'none',
                fontSize: isMobile ? '16px' : '16px',
                fontWeight: 'bold',
              }}
            >
              {isLoading ? '注册中...' : '注册账号'}
            </Button>
          </Form.Item>
        </Form>

        {!isMobile && (
          <>
            <Divider style={{ margin: '24px 0' }}>
              <Text type="secondary" style={{ fontSize: '14px' }}>
                或
              </Text>
            </Divider>

            {/* 登录链接 */}
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <Text style={{ fontSize: '14px', color: '#666' }}>
                已有账号？
                <Link to="/auth/login" style={{ marginLeft: '8px', fontWeight: 'bold' }}>
                  立即登录
                </Link>
              </Text>
            </div>
          </>
        )}

        {/* 注册说明 */}
        <Alert
          message={
            <Space>
              <InfoCircleOutlined />
              <span style={{ fontSize: '12px' }}>
                注册即表示您同意我们的
                <a href="https://www.quantmindai.cn/terms" target="_blank" rel="noopener noreferrer" style={{ margin: '0 4px' }}>服务条款</a>
                和
                <a href="https://www.quantmindai.cn/privacy" target="_blank" rel="noopener noreferrer" style={{ margin: '0 4px' }}>隐私政策</a>
              </span>
            </Space>
          }
          type="info"
          showIcon={false}
          style={{ fontSize: '12px' }}
        />

        {/* 移动端登录链接 */}
        {isMobile && (
          <div style={{ textAlign: 'center', marginTop: '24px' }}>
            <Text style={{ fontSize: '14px', color: '#666' }}>
              已有账号？
              <Link to="/auth/login" style={{ marginLeft: '8px', fontWeight: 'bold' }}>
                立即登录
              </Link>
            </Text>
          </div>
        )}
      </Card>

      {!isMobile && (
        <div
          style={{
            position: 'absolute',
            bottom: '20px',
            left: '0',
            right: '0',
            textAlign: 'center',
            color: 'white',
            fontSize: '12px',
          }}
        >
          <Space split={<span style={{ color: 'rgba(255,255,255,0.3)' }}>|</span>}>
            <a href="https://www.quantmindai.cn/privacy" target="_blank" rel="noopener noreferrer" style={{ color: 'white', textDecoration: 'none' }}>隐私政策</a>
            <a href="https://www.quantmindai.cn/terms" target="_blank" rel="noopener noreferrer" style={{ color: 'white', textDecoration: 'none' }}>服务条款</a>
            <a href="https://www.quantmindai.cn/help" target="_blank" rel="noopener noreferrer" style={{ color: 'white', textDecoration: 'none' }}>帮助中心</a>
            <span>© 2026 QuantMind</span>
          </Space>
        </div>
      )}
    </div>
  );
};

export default RegisterPage;
