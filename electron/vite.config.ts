import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiBase = process.env.VITE_API_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000';
const wsBase = process.env.VITE_WS_BASE_URL || apiBase.replace(/^http/, 'ws');

export default defineConfig(({ mode }) => {
  return {
    base: mode === 'production' ? './' : '/',
    plugins: [react()],
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/setupTests.ts',
      coverage: {
        reporter: ['text', 'json', 'html'],
        exclude: [
          'node_modules/',
          'src/setupTests.ts',
        ]
      }
    },
    define: {
      'process.env.NODE_ENV': JSON.stringify(mode),
      'process.env.VITE_DEV': JSON.stringify(process.env.VITE_DEV || '0'),
      'process.env.VITE_API_BASE_URL': JSON.stringify(apiBase),
      'process.env.VITE_WS_BASE_URL': JSON.stringify(wsBase),
      'process.env.REACT_APP_API_BASE_URL': JSON.stringify(process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'),
      // OSS Edition - local storage only
      'process.env.COS_SECRET_ID': JSON.stringify(''),
      'process.env.COS_SECRET_KEY': JSON.stringify(''),
      'process.env.COS_BUCKET': JSON.stringify(''),
      'process.env.COS_REGION': JSON.stringify(''),
      'process.env.TENCENT_SECRET_ID': JSON.stringify(''),
      'process.env.TENCENT_SECRET_KEY': JSON.stringify(''),
      'process.env.TENCENT_BUCKET': JSON.stringify(''),
      'process.env.TENCENT_REGION': JSON.stringify(''),
      'process.env.TENCENT_COS_URL': JSON.stringify(''),
      'process.env.VITE_TENCENT_COS_URL': JSON.stringify(''),
    },
    build: {
      outDir: 'dist-react',
      sourcemap: mode === 'development',
      rollupOptions: {
        input: {
          main: 'index.html'
        }
      }
    },
    server: {
      port: parseInt(process.env.VITE_PORT || '3000'),
      strictPort: true, // 固定使用指定端口（默认 3000），占用则直接报错
      host: '127.0.0.1',
      proxy: {
        '/api/tencent': {
          target: 'https://qt.gtimg.cn',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/tencent/, ''),
          configure: (proxy, options) => {
            proxy.on('proxyReq', (proxyReq, req, res) => {
              proxyReq.setHeader('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
            });
          }
        }
      }
    }
  };
});
