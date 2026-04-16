/**
 * 认证路由配置示例
 * 展示如何在应用中集成认证系统
 */

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import {
  LoginPage,
  RegisterPage,
  ForgotPasswordPage,
  ResetPasswordPage,
  MFAVerificationPage,
  MFASetupPage,
  PageLoading
} from './components';

const AppRoutes: React.FC = () => {
  console.log('AppRoutes: 组件渲染，当前路径:', window.location.pathname);

  return (
    <Routes>
      {/* 公开认证路由 */}
      <Route path="login" element={<LoginPage />} />
      <Route path="register" element={<RegisterPage />} />
      <Route path="forgot-password" element={<ForgotPasswordPage />} />
      <Route path="reset-password" element={<ResetPasswordPage />} />
      <Route path="mfa/verify" element={<MFAVerificationPage />} />
      <Route path="mfa/setup" element={<MFASetupPage />} />

      {/* 默认重定向到登录页 */}
      <Route path="*" element={<Navigate to="/auth/login" replace />} />
    </Routes>
  );
};

export default AppRoutes;
