#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

console.log('🔍 404错误诊断工具');
console.log('==================');

// 1. 检查关键文件是否存在
console.log('\n📁 检查关键文件:');

const filesToCheck = [
  'src/main.tsx',
  'src/App.tsx',
  'dist-react/index.html',
  'dist-react/assets/index-DYAsDz6q.js',
  'dist-react/assets/index-CAOLOmN4.css',
  'vite.config.ts'
];

filesToCheck.forEach(file => {
  const exists = fs.existsSync(file);
  console.log(`${exists ? '✅' : '❌'} ${file}`);
  if (exists) {
    const stats = fs.statSync(file);
    console.log(`   大小: ${(stats.size / 1024).toFixed(2)} KB`);
  }
});

// 2. 检查index.html内容
console.log('\n📄 检查 index.html 内容:');
if (fs.existsSync('dist-react/index.html')) {
  const indexContent = fs.readFileSync('dist-react/index.html', 'utf8');
  console.log('  标题:', indexContent.match(/<title>(.*?)<\/title>/)?.[1] || '未找到');
  console.log('  root元素:', indexContent.includes('<div id="root">') ? '✅ 存在' : '❌ 缺失');
  console.log('  JS文件:', indexContent.match(/src="([^"]+\.js)"/)?.[1] || '未找到');
  console.log('  CSS文件:', indexContent.match(/href="([^"]+\.css)"/)?.[1] || '未找到');
}

// 3. 检查package.json中的依赖
console.log('\n📦 检查关键依赖:');
if (fs.existsSync('package.json')) {
  const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  const depsToCheck = ['react', 'react-dom', 'framer-motion', 'recoil', 'antd', '@emotion/is-prop-valid'];

  depsToCheck.forEach(dep => {
    const isInstalled = packageJson.dependencies?.[dep] || packageJson.devDependencies?.[dep];
    console.log(`${isInstalled ? '✅' : '❌'} ${dep}: ${isInstalled || '未安装'}`);
  });
}

// 4. 检查路由配置
console.log('\n🛣️ 检查路由配置:');
const appTsPath = 'src/App.tsx';
if (fs.existsSync(appTsPath)) {
  const appContent = fs.readFileSync(appTsPath, 'utf8');
  console.log('  BrowserRouter:', appContent.includes('BrowserRouter') ? '✅ 存在' : '❌ 缺失');
  console.log('  Routes:', appContent.includes('Routes') || appContent.includes('<Route') ? '✅ 存在' : '❌ 缺失');
}

// 5. 检查构建输出
console.log('\n🏗️ 检查构建输出:');
if (fs.existsSync('dist-react')) {
  const assetFiles = fs.readdirSync('dist-react/assets');
  console.log(`  资源文件数量: ${assetFiles.length}`);
  console.log('  主要JS文件:', assetFiles.filter(f => f.includes('index-') && f.endsWith('.js')));
  console.log('  主要CSS文件:', assetFiles.filter(f => f.includes('index-') && f.endsWith('.css')));
}

console.log('\n🎯 诊断建议:');
console.log('1. 如果依赖缺失，运行: npm install');
console.log('2. 如果构建文件缺失，运行: npm run build:react');
console.log('3. 检查控制台是否有JavaScript错误');
console.log('4. 确认端口3000没有被占用');

console.log('\n🔧 常见修复方案:');
console.log('1. 重新安装依赖: npm install');
console.log('2. 重新构建: npm run build:react');
console.log('3. 清理缓存: npm run build -- --force');
console.log('4. 检查路由配置是否正确');

console.log('\n✨ 诊断完成!');
