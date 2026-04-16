/**
 * QlibBacktestService 单元测试
 */

import { describe, it, expect } from 'vitest';
import { qlibBacktestService, QlibBacktestError } from '../qlibBacktestService';
import type { QlibBacktestConfig } from '../../../types/backtest/qlib';

describe('QlibBacktestService', () => {
  describe('配置验证', () => {
    it('应该拒绝空的开始日期', async () => {
      const config: QlibBacktestConfig = {
        symbol: '',
        start_date: '',
        end_date: '2024-12-31',
        initial_capital: 1000000,
        user_id: 'test_user',
        qlib_strategy_type: 'TopkDropout',
        qlib_strategy_params: {},
      };

      await expect(qlibBacktestService.runBacktest(config)).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('应该拒绝无效的日期范围', async () => {
      const config: QlibBacktestConfig = {
        symbol: '000001.SZ',
        start_date: '2024-12-31',
        end_date: '2024-01-01',
        initial_capital: 1000000,
        user_id: 'test_user',
        qlib_strategy_type: 'TopkDropout',
        qlib_strategy_params: {},
      };

      await expect(qlibBacktestService.runBacktest(config)).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('应该拒绝非正的初始资金', async () => {
      const config: QlibBacktestConfig = {
        symbol: '000001.SZ',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 0,
        user_id: 'test_user',
        qlib_strategy_type: 'TopkDropout',
        qlib_strategy_params: {},
      };

      await expect(qlibBacktestService.runBacktest(config)).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('应该正确分类VALIDATION_ERROR', async () => {
      const config: QlibBacktestConfig = {
        symbol: '000001.SZ',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 1000000,
        user_id: '',
        qlib_strategy_type: 'TopkDropout',
        qlib_strategy_params: {},
      };

      try {
        await qlibBacktestService.runBacktest(config);
      } catch (error) {
        expect(error).toBeInstanceOf(QlibBacktestError);
        expect((error as QlibBacktestError).code).toBe('VALIDATION_ERROR');
      }
    });
  });

  describe('API参数验证', () => {
    it('getResult应该拒绝空的backtestId', async () => {
      await expect(qlibBacktestService.getResult('')).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('deleteBacktest应该拒绝空的backtestId', async () => {
      await expect(qlibBacktestService.deleteBacktest('', 'test_user')).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('getHistory应该拒绝空的userId', async () => {
      await expect(qlibBacktestService.getHistory('')).rejects.toThrow(
        QlibBacktestError
      );
    });

    it('compareBacktests应该拒绝空的ID', async () => {
      await expect(
        qlibBacktestService.compareBacktests('', 'id2', 'test_user')
      ).rejects.toThrow(QlibBacktestError);

      await expect(
        qlibBacktestService.compareBacktests('id1', '', 'test_user')
      ).rejects.toThrow(QlibBacktestError);
    });
  });

  describe('WebSocket管理', () => {
    it('connectProgress应该拒绝空的backtestId', () => {
      expect(() => {
        qlibBacktestService.connectProgress('', {});
      }).toThrow(QlibBacktestError);
    });

    it('isProgressConnected应该返回false对于未连接的ID', () => {
      expect(qlibBacktestService.isProgressConnected('non-existent')).toBe(false);
    });
  });
});
