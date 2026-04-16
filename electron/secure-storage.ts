/**
 * Electron 安全存储
 * 使用 electron-store 和 safeStorage API 实现安全的密钥持久化
 */

import { app, safeStorage } from 'electron';
import Store from 'electron-store';
import { secureStorage } from '../backend/services/SecureStorage';

/**
 * 加密存储配置
 */
interface SecureStoreSchema {
  // 主密钥盐值
  masterKeySalt: string;
  // 加密的存储数据
  encryptedData: string;
  // 元数据
  metadata: {
    version: string;
    createdAt: number;
    updatedAt: number;
  };
}

/**
 * Electron 安全存储管理器
 */
export class ElectronSecureStorage {
  private store: Store<SecureStoreSchema>;
  private initialized = false;

  constructor() {
    // 配置 electron-store
    this.store = new Store<SecureStoreSchema>({
      name: 'secure-storage',
      encryptionKey: this.getEncryptionKey(),
      defaults: {
        masterKeySalt: '',
        encryptedData: '',
        metadata: {
          version: '1.0',
          createdAt: Date.now(),
          updatedAt: Date.now()
        }
      }
    });
  }

  /**
   * 获取加密密钥
   * 使用 Electron safeStorage API（如果可用）
   */
  private getEncryptionKey(): string {
    // 检查 safeStorage 是否可用
    if (safeStorage.isEncryptionAvailable()) {
      // 使用系统提供的加密
      return 'electron-safe-storage-key';
    } else {
      // 降级方案：使用固定密钥（不推荐用于生产环境）
      console.warn('safeStorage is not available, using fallback encryption');
      return 'fallback-encryption-key-change-in-production';
    }
  }

  /**
   * 初始化安全存储
   * @param password - 用户密码
   */
  async initialize(password: string): Promise<void> {
    // 获取或创建盐值
    let salt = this.store.get('masterKeySalt');

    if (!salt) {
      // 首次初始化，创建新盐值
      salt = await secureStorage.initialize(password);
      this.store.set('masterKeySalt', salt);
    } else {
      // 使用现有盐值初始化
      await secureStorage.initialize(password, salt);
    }

    // 尝试加载现有数据
    await this.loadData();

    this.initialized = true;
  }

  /**
   * 保存数据到持久化存储
   */
  async saveData(): Promise<void> {
    if (!this.initialized) {
      throw new Error('ElectronSecureStorage not initialized');
    }

    // 导出加密数据
    const data = await secureStorage.exportData();

    // 使用 safeStorage 进一步加密（如果可用）
    let encryptedData: string;

    if (safeStorage.isEncryptionAvailable()) {
      const buffer = safeStorage.encryptString(data);
      encryptedData = buffer.toString('base64');
    } else {
      // 降级方案：直接存储（已经被 SecureStorage 加密）
      encryptedData = data;
    }

    // 保存到 electron-store
    this.store.set('encryptedData', encryptedData);
    this.store.set('metadata', {
      ...this.store.get('metadata'),
      updatedAt: Date.now()
    });
  }

  /**
   * 从持久化存储加载数据
   */
  async loadData(): Promise<void> {
    const encryptedData = this.store.get('encryptedData');

    if (!encryptedData) {
      // 没有数据，跳过
      return;
    }

    // 解密数据
    let data: string;

    if (safeStorage.isEncryptionAvailable()) {
      try {
        const buffer = Buffer.from(encryptedData, 'base64');
        data = safeStorage.decryptString(buffer);
      } catch (error) {
        console.error('Failed to decrypt data with safeStorage:', error);
        // 降级处理
        data = encryptedData;
      }
    } else {
      data = encryptedData;
    }

    // 导入到 SecureStorage
    await secureStorage.importData(data);
  }

  /**
   * 存储 API 密钥
   */
  async storeApiKey(
    keyId: string,
    keyValue: string,
    metadata: {
      name: string;
      permissions: string[];
      expiresAt?: number;
    }
  ): Promise<void> {
    await secureStorage.storeApiKey(keyId, keyValue, metadata);
    await this.saveData();
  }

  /**
   * 获取 API 密钥
   */
  async getApiKey(keyId: string, requiredPermissions?: string[]): Promise<string> {
    return await secureStorage.getApiKey(keyId, requiredPermissions);
  }

  /**
   * 更新 API 密钥
   */
  async updateApiKey(
    keyId: string,
    newValue?: string,
    updates?: { name?: string; permissions?: string[]; expiresAt?: number }
  ): Promise<void> {
    await secureStorage.updateApiKey(keyId, newValue, updates);
    await this.saveData();
  }

  /**
   * 删除 API 密钥
   */
  async deleteApiKey(keyId: string): Promise<void> {
    await secureStorage.deleteApiKey(keyId);
    await this.saveData();
  }

  /**
   * 列出所有密钥
   */
  listApiKeys() {
    return secureStorage.listApiKeys();
  }

  /**
   * 密钥轮换
   */
  async rotateApiKey(keyId: string, newValue: string): Promise<void> {
    await secureStorage.rotateApiKey(keyId, newValue);
    await this.saveData();
  }

  /**
   * 清理过期密钥
   */
  async cleanupExpiredKeys(): Promise<number> {
    const count = secureStorage.cleanupExpiredKeys();
    if (count > 0) {
      await this.saveData();
    }
    return count;
  }

  /**
   * 获取访问日志
   */
  getAccessLog(keyId?: string) {
    return secureStorage.getAccessLog(keyId);
  }

  /**
   * 清除所有数据
   */
  async clear(): Promise<void> {
    secureStorage.clear();
    this.store.clear();
    this.initialized = false;
  }

  /**
   * 检查是否已初始化
   */
  isInitialized(): boolean {
    return this.initialized;
  }

  /**
   * 更改主密码
   */
  async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    // 验证旧密码
    const salt = this.store.get('masterKeySalt');
    await secureStorage.initialize(oldPassword, salt);

    // 尝试解密一个密钥来验证密码正确性
    const keys = secureStorage.listApiKeys();
    if (keys.length > 0) {
      try {
        await secureStorage.getApiKey(keys[0].id);
      } catch (error) {
        throw new Error('Invalid old password');
      }
    }

    // 导出所有数据
    const data = await secureStorage.exportData();

    // 使用新密码重新初始化
    const newSalt = await secureStorage.initialize(newPassword);
    this.store.set('masterKeySalt', newSalt);

    // 重新导入数据（会使用新密钥重新加密）
    await secureStorage.importData(data);
    await this.saveData();
  }
}

// 导出单例实例
export const electronSecureStorage = new ElectronSecureStorage();

// 自动保存定时器
let autoSaveTimer: NodeJS.Timeout | null = null;

/**
 * 启用自动保存
 * @param intervalMs - 保存间隔（毫秒）
 */
export function enableAutoSave(intervalMs: number = 60000): void {
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer);
  }

  autoSaveTimer = setInterval(async () => {
    try {
      await electronSecureStorage.saveData();
    } catch (error) {
      console.error('Auto-save failed:', error);
    }
  }, intervalMs);
}

/**
 * 禁用自动保存
 */
export function disableAutoSave(): void {
  if (autoSaveTimer) {
    clearInterval(autoSaveTimer);
    autoSaveTimer = null;
  }
}

// 应用退出时保存数据
app.on('before-quit', async () => {
  try {
    await electronSecureStorage.saveData();
  } catch (error) {
    console.error('Failed to save data on quit:', error);
  }
});
