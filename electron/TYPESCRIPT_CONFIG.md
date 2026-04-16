
# TypeScript 配置说明

本项目使用多个TypeScript配置文件来管理不同部分的代码：

## 配置文件说明

### 1. tsconfig.json
- **用途**: React渲染进程的主要TypeScript配置
- **包含**: src/ 目录下的所有TypeScript文件
- **排除**: electron目录、编译输出目录和测试文件

### 2. tsconfig.combined.json
- **用途**: 共享的TypeScript编译选项
- **包含**: src/ 目录下的所有TypeScript文件
- **说明**: 被tsconfig.json继承，提供通用的编译选项

### 3. tsconfig.electron.json
- **用途**: Electron主进程的TypeScript配置
- **包含**: electron/ 目录下的所有TypeScript文件
- **排除**: src目录和编译输出目录
- **输出**: dist-electron/ 目录

### 4. .vscode/tsconfig.json
- **用途**: VSCode工作区的TypeScript配置
- **包含**: src/ 目录下的所有TypeScript文件
- **说明**: 确保VSCode使用正确的TypeScript配置进行类型检查

## 编译命令

```bash
# 类型检查（不生成输出）
npm run typecheck

# 编译React渲染进程
npm run build:react

# 编译Electron主进程
npm run build:electron

# 同时编译React和Electron
npm run build
```

## VSCode配置

项目包含以下VSCode配置文件：

- `.vscode/settings.json`: 工作区设置
- `.vscode/extensions.json`: 推荐扩展
- `.vscode/tsconfig.json`: VSCode的TypeScript配置

## 注意事项

1. **不要修改编译输出文件**: dist/、dist-react/ 和 dist-electron/ 目录下的文件是编译生成的，不应手动修改

2. **TypeScript配置分离**: Electron主进程和React渲染进程使用不同的TypeScript配置，确保类型检查和编译的正确性

3. **避免配置冲突**: tsconfig.json 和 tsconfig.electron.json 分别处理不同的代码部分，避免重复包含

4. **使用相对导入**: 在src/目录内的文件使用相对路径导入，确保打包后的路径正确
